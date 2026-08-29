#include <algorithm>
#include <atomic>
#include <format>
#include <iostream>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "MysqlConnection.hpp"
#include "mysql_settings.hpp"

using namespace std;

constexpr int BATCH_SIZE = 1000;

const int detected_threads = thread::hardware_concurrency();
const int N_THREADS = max(2, detected_threads) - 1;

struct EcoLine {
  int id;
  string uci;
};

void processBatch(mysql::Connection &conn, const string &table,
                  const vector<EcoLine> &eco_lines, int start_id, int end_id,
                  atomic<int> &total_updated) {
  string query = format("SELECT id, moves_blob FROM {} "
                        "WHERE id >= {} AND id < {} AND ecoID IS NULL "
                        "ORDER BY id ASC LIMIT {}",
                        table, start_id, end_id, BATCH_SIZE);

  try {
    auto result = conn.queryResult(query);

    vector<pair<int, int>> updates;
    MYSQL_ROW row;

    while ((row = result.fetchRow())) {
      unsigned long *lengths = result.fetchLengths();

      if (!row[0] || !row[1]) {
        continue;
      }

      string moves_blob(row[1], lengths[1]);

      auto it =
          find_if(eco_lines.begin(), eco_lines.end(), [&](const auto &eco) {
            return moves_blob.rfind(eco.uci, 0) == 0;
          });

      if (it != eco_lines.end()) {
        int game_id = atoi(row[0]);
        updates.emplace_back(it->id, game_id);
      }
    }

    if (updates.empty()) {
      return;
    }

    for (const auto &[eco_id, game_id] : updates) {
      string update_query = format("UPDATE {} SET ecoID = {} WHERE id = {}",
                                   table, eco_id, game_id);

      conn.query(update_query);
    }

    total_updated += static_cast<int>(updates.size());

  } catch (const exception &e) {
    cerr << "Batch error: " << e.what() << '\n';
  }
}

void classify_worker(const string &table, const vector<EcoLine> &eco_lines,
                     int start_id, int end_id, atomic<int> &total_updated) {
  try {
    mysql::Connection conn(mysql_host, mysql_user, mysql_password, database);

    int last_id = start_id;

    while (last_id < end_id) {
      processBatch(conn, table, eco_lines, last_id, end_id, total_updated);
      last_id += BATCH_SIZE;

      if (last_id + BATCH_SIZE > end_id) {
        last_id = end_id;
      }
    }

  } catch (const exception &e) {
    cerr << "Connection error: " << e.what() << '\n';
  }
}

int main(int argc, const char *argv[]) {
  string table = "all_games";

  if (argc > 1) {
    table = argv[1];
  }

  cout << "Using table: " << table << '\n';

  try {
    mysql::Connection conn(mysql_host, mysql_user, mysql_password, database);

    auto res = conn.queryResult("SELECT id, uci FROM eco "
                                "WHERE uci IS NOT NULL "
                                "ORDER BY LENGTH(uci) DESC");

    vector<EcoLine> eco_lines;
    MYSQL_ROW row;

    while ((row = res.fetchRow())) {
      if (!row[0] || !row[1]) {
        continue;
      }

      eco_lines.emplace_back(atoi(row[0]), row[1]);
    }

    string minmax_query = format("SELECT MIN(id), MAX(id) FROM {} "
                                 "WHERE ecoID IS NULL",
                                 table);

    auto minmax = conn.queryResult(minmax_query);

    int min_id = 0;
    int max_id = 0;

    if ((row = minmax.fetchRow())) {
      if (row[0]) {
        min_id = atoi(row[0]);
      }
      if (row[1]) {
        max_id = atoi(row[1]);
      }
    }

    int total_range = max_id - min_id + 1;
    int chunk_size = (total_range + N_THREADS - 1) / N_THREADS;

    vector<thread> threads;
    atomic total_updated = 0;

    for (int i = 0; i < N_THREADS; ++i) {
      int start_id = min_id + i * chunk_size;
      int end_id = min(start_id + chunk_size - 1, max_id);
      threads.emplace_back(classify_worker, cref(table), cref(eco_lines),
                           start_id, end_id + 1, ref(total_updated));
    }

    for (auto &t : threads) {
      if (t.joinable()) {
        t.join();
      }
    }

    cout << "Done. Updated: " << total_updated << '\n';
  } catch (const exception &e) {
    cerr << "Error: " << e.what() << '\n';
    return 1;
  }

  return 0;
}
