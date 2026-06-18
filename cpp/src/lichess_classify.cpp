#include <algorithm>
#include <atomic>
#include <cstring>
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
  char query[1024];

  while (last_id < end_id) {

    snprintf(query, sizeof(query),
             "SELECT id, moves_blob FROM %s "
             "WHERE id >= %d AND id < %d AND ecoID IS NULL "
             "ORDER BY id ASC LIMIT %d",
             table.c_str(), last_id, end_id, BATCH_SIZE);

    if (mysql_query(conn, query)) {
      cerr << "Query error: " << mysql_error(conn) << "\n";
      break;
    }

    MYSQL_RES *result = mysql_store_result(conn);
    if (!result) {
      cerr << "Store result error: " << mysql_error(conn) << "\n";
      break;
    }

    vector<pair<int, int>> updates;
    MYSQL_ROW row;

    while ((row = mysql_fetch_row(result))) {

      if (!row[0])
        continue;

      int game_id = atoi(row[0]);
      last_id = game_id;

      const char *moves_cstr = row[1];
      if (!moves_cstr) {
        moves_cstr = "";
      }

      string moves_blob(moves_cstr);

      for (const auto &eco : eco_lines) {
        if (moves_blob.rfind(eco.uci, 0) == 0) {
          updates.emplace_back(eco.id, game_id);
          break;
        }
      }
    }

    mysql_free_result(result);

    if (updates.empty())
      break;

    for (const auto &upd : updates) {
      char q[256];
      snprintf(q, sizeof(q), "UPDATE %s SET ecoID = %d WHERE id = %d",
               table.c_str(), upd.first, upd.second);

      if (mysql_query(conn, q)) {
        cerr << "Update error: " << mysql_error(conn) << "\n";
      }
    }

    total_updated += updates.size();

    if (updates.size() < BATCH_SIZE)
      break;
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
    if (!row[0] || !row[1])
      continue;

    eco_lines.push_back({atoi(row[0]), string(row[1])});
  }

  mysql_free_result(res);

  char minmax[256];
  snprintf(minmax, sizeof(minmax),
           "SELECT MIN(id), MAX(id) FROM %s WHERE ecoID IS NULL",
           table.c_str());

  if (mysql_query(conn, minmax)) {
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

  int min_id = 0, max_id = 0;

  if ((row = mysql_fetch_row(res))) {
    if (row[0])
      min_id = atoi(row[0]);
    if (row[1])
      max_id = atoi(row[1]);
  }

  mysql_free_result(res);
  mysql_close(conn);

  int total_range = max_id - min_id + 1;
  int chunk_size = (total_range + N_THREADS - 1) / N_THREADS;

  vector<thread> threads;
  atomic<int> total_updated = 0;

  for (int i = 0; i < N_THREADS; ++i) {
    int start_id = min_id + i * chunk_size;
    int end_id = min(min_id + (i + 1) * chunk_size - 1, max_id);

    threads.emplace_back(classify_worker, table, cref(eco_lines), start_id,
                         end_id + 1, ref(total_updated));
  }

  for (auto &t : threads)
    t.join();

  cout << "Done. Updated: " << total_updated << "\n";

  return 0;
}
