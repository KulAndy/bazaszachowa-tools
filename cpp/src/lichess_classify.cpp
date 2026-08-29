#include <algorithm>
#include <atomic>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include <cppconn/connection.h>
#include <cppconn/exception.h>
#include <cppconn/prepared_statement.h>
#include <cppconn/resultset.h>
#include <mysql_connection.h>
#include <mysql_driver.h>

#include "mysql_settings.hpp"

using namespace std;

constexpr int BATCH_SIZE = 1000;

const int detected_threads = thread::hardware_concurrency();
const int N_THREADS = max(2, detected_threads) - 1;

struct EcoLine {
  int id;
  string uci;

  EcoLine(int id, const string &uci) : id(id), uci(uci) {}
};

void processBatch(sql::Connection *conn, const string &table,
                  const vector<EcoLine> &eco_lines, int start_id, int end_id,
                  atomic<int> &total_updated) {
  string select_query = "SELECT id, moves_blob FROM " + table +
                        " WHERE id >= ? AND id < ? AND ecoID IS NULL "
                        "ORDER BY id ASC LIMIT ?";
  unique_ptr<sql::PreparedStatement> select_stmt(
      conn->prepareStatement(select_query));
  select_stmt->setInt(1, start_id);
  select_stmt->setInt(2, end_id);
  select_stmt->setInt(3, BATCH_SIZE);

  unique_ptr<sql::ResultSet> result(select_stmt->executeQuery());

  vector<pair<int, int>> updates;

  while (result->next()) {
    int game_id = result->getInt("id");
    string moves_blob = result->getString("moves_blob");

    auto it =
        find_if(eco_lines.begin(), eco_lines.end(), [&](const EcoLine &eco) {
          return moves_blob.rfind(eco.uci, 0) == 0;
        });

    if (it != eco_lines.end()) {
      updates.emplace_back(it->id, game_id);
    }
  }

  if (updates.empty()) {
    return;
  }

  string update_query = "UPDATE " + table + " SET ecoID = ? WHERE id = ?";
  unique_ptr<sql::PreparedStatement> update_stmt(
      conn->prepareStatement(update_query));

  for (const auto &[eco_id, game_id] : updates) {
    update_stmt->setInt(1, eco_id);
    update_stmt->setInt(2, game_id);
    update_stmt->executeUpdate();
  }

  total_updated += updates.size();
}

void classify_worker(const string &table, const vector<EcoLine> &eco_lines,
                     int start_id, int end_id, atomic<int> &total_updated) {
  try {
    sql::mysql::MySQL_Driver *driver = sql::mysql::get_driver_instance();
    unique_ptr<sql::Connection> conn(
        driver->connect(mysql_host, mysql_user, mysql_password));
    conn->setSchema(database);

    int last_id = start_id;
    while (last_id < end_id) {
      processBatch(conn.get(), table, eco_lines, last_id, end_id,
                   total_updated);
      last_id += BATCH_SIZE;

      if (last_id + BATCH_SIZE > end_id) {
        last_id = end_id;
      }
    }
  } catch (const sql::SQLException &e) {
    cerr << "Connection error: " << e.what()
         << " (MySQL error code: " << e.getErrorCode()
         << ", SQLState: " << e.getSQLState() << ")\n";
  }
}

int main(int argc, const char *argv[]) {
  string table = "all_games";
  if (argc > 1) {
    table = argv[1];
  }

  cout << "Using table: " << table << "\n";

  try {
    sql::mysql::MySQL_Driver *driver = sql::mysql::get_driver_instance();
    unique_ptr<sql::Connection> conn(
        driver->connect(mysql_host, mysql_user, mysql_password));
    conn->setSchema(database);

    unique_ptr<sql::Statement> stmt(conn->createStatement());
    unique_ptr<sql::ResultSet> res(
        stmt->executeQuery("SELECT id, uci FROM eco "
                           "WHERE uci IS NOT NULL "
                           "ORDER BY LENGTH(uci) DESC"));

    vector<EcoLine> eco_lines;
    while (res->next()) {
      eco_lines.emplace_back(res->getInt("id"), res->getString("uci"));
    }

    ostringstream minmax_query;
    minmax_query << "SELECT MIN(id), MAX(id) FROM " << table
                 << " WHERE ecoID IS NULL";
    unique_ptr<sql::ResultSet> minmax(stmt->executeQuery(minmax_query.str()));

    int min_id = 0;
    int max_id = 0;
    if (minmax->next()) {
      min_id = minmax->getInt(1);
      max_id = minmax->getInt(2);
    }

    int total_range = max_id - min_id + 1;
    int chunk_size = (total_range + N_THREADS - 1) / N_THREADS;

    vector<thread> threads;
    atomic<int> total_updated{0};

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

    cout << "Done. Updated: " << total_updated << "\n";
  } catch (const sql::SQLException &e) {
    cerr << "MySQL error: " << e.what()
         << " (MySQL error code: " << e.getErrorCode()
         << ", SQLState: " << e.getSQLState() << ")\n";
    return 1;
  } catch (const exception &e) {
    cerr << "Exception: " << e.what() << "\n";
    return 1;
  }

  return 0;
}
