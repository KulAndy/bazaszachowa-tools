#include <algorithm>
#include <atomic>
#include <format>
#include <iostream>
#include <memory>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "mysql_settings.hpp"
#include <mysql/mysql.h>

using namespace std;

constexpr int BATCH_SIZE = 1000;

const int detected_threads = thread::hardware_concurrency();
const int N_THREADS = max(2, detected_threads) - 1;

struct EcoLine {
  int id;
  string uci;
};

void processBatch(MYSQL *conn, const string &table,
                  const vector<EcoLine> &eco_lines, int start_id, int end_id,
                  atomic<int> &total_updated) {
  string query = format("SELECT id, moves_blob FROM {} "
                        "WHERE id >= {} AND id < {} AND ecoID IS NULL "
                        "ORDER BY id ASC LIMIT {}",
                        table, start_id, end_id, BATCH_SIZE);

  if (mysql_query(conn, query.c_str())) {
    cerr << "Query error: " << mysql_error(conn) << "\n";
    return;
  }

  MYSQL_RES *result = mysql_store_result(conn);
  if (!result) {
    cerr << "Store result error: " << mysql_error(conn) << "\n";
    return;
  }

  vector<pair<int, int>> updates;
  MYSQL_ROW row;

  while ((row = mysql_fetch_row(result))) {
    if (!row[0]) {
      continue;
    }

    int game_id = atoi(row[0]);
    const char *moves_cstr = row[1] ? row[1] : "";
    string moves_blob(moves_cstr);

    for (const auto &eco : eco_lines) {
      if (moves_blob.rfind(eco.uci, 0) == 0) {
        updates.emplace_back(eco.id, game_id);
        break;
      }
    }
  }

  mysql_free_result(result);

  if (updates.empty()) {
    return;
  }

  for (const auto &[eco_id, game_id] : updates) {
    string update_query = format("UPDATE {} SET ecoID = {} WHERE id = {}",
                                 table, eco_id, game_id);

    if (mysql_query(conn, update_query.c_str())) {
      cerr << "Update error: " << mysql_error(conn) << "\n";
    }
  }

  total_updated += updates.size();
}

void classify_worker(const string &table, const vector<EcoLine> &eco_lines,
                     int start_id, int end_id, atomic<int> &total_updated) {
  MYSQL *conn = mysql_init(nullptr);
  if (!conn) {
    cerr << "mysql_init failed\n";
    return;
  }

  if (!mysql_real_connect(conn, mysql_host, mysql_user, mysql_password,
                          database, 0, nullptr, 0)) {
    cerr << "Connection error: " << mysql_error(conn) << "\n";
    mysql_close(conn);
    return;
  }

  int last_id = start_id;
  while (last_id < end_id) {
    processBatch(conn, table, eco_lines, last_id, end_id, total_updated);
    last_id += BATCH_SIZE;

    if (last_id + BATCH_SIZE > end_id) {
      last_id = end_id;
    }
  }

  mysql_close(conn);
}

int main(int argc, char *argv[]) {
  string table = "all_games";
  if (argc > 1)
    table = argv[1];

  cout << "Using table: " << table << "\n";

  MYSQL *conn = mysql_init(nullptr);
  if (!conn)
    return 1;

  if (!mysql_real_connect(conn, mysql_host, mysql_user, mysql_password,
                          database, 0, nullptr, 0)) {
    cerr << mysql_error(conn) << "\n";
    mysql_close(conn);
    return 1;
  }

  if (mysql_query(conn, "SELECT id, uci FROM eco WHERE uci IS NOT NULL ORDER "
                        "BY LENGTH(uci) DESC")) {
    cerr << mysql_error(conn) << "\n";
    mysql_close(conn);
    return 1;
  }

  MYSQL_RES *res = mysql_store_result(conn);
  if (!res) {
    cerr << mysql_error(conn) << "\n";
    mysql_close(conn);
    return 1;
  }

  vector<EcoLine> eco_lines;
  MYSQL_ROW row;

  while ((row = mysql_fetch_row(res))) {
    if (!row[0] || !row[1]) {
      continue;
    }
    eco_lines.emplace_back(atoi(row[0]), row[1]);
  }

  mysql_free_result(res);

  string minmax_query =
      format("SELECT MIN(id), MAX(id) FROM {} WHERE ecoID IS NULL", table);

  if (mysql_query(conn, minmax_query.c_str())) {
    cerr << mysql_error(conn) << "\n";
    mysql_close(conn);
    return 1;
  }

  res = mysql_store_result(conn);
  if (!res) {
    cerr << mysql_error(conn) << "\n";
    mysql_close(conn);
    return 1;
  }

  int min_id = 0;
  int max_id = 0;

  if ((row = mysql_fetch_row(res))) {
    if (row[0]) {
      min_id = atoi(row[0]);
    }
    if (row[1]) {
      max_id = atoi(row[1]);
    }
  }

  mysql_free_result(res);
  mysql_close(conn);

  int total_range = max_id - min_id + 1;
  int chunk_size = (total_range + N_THREADS - 1) / N_THREADS;

  vector<jthread> threads;
  atomic total_updated = 0;

  for (int i = 0; i < N_THREADS; ++i) {
    int start_id = min_id + i * chunk_size;
    int end_id = min(start_id + chunk_size - 1, max_id);
    threads.emplace_back(classify_worker, cref(table), cref(eco_lines),
                         start_id, end_id + 1, ref(total_updated));
  }

  cout << "Done. Updated: " << total_updated << "\n";
  return 0;
}
