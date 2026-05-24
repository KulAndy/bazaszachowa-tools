#include <atomic>
#include <iostream>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include <cppconn/prepared_statement.h>
#include <cppconn/resultset.h>
#include <cppconn/statement.h>
#include <mysql_connection.h>
#include <mysql_driver.h>

#include "mysql_settings.hpp"

using namespace std;

constexpr int BATCH_SIZE = 1000;
const unsigned int detected_threads = thread::hardware_concurrency();
const unsigned int N_THREADS = max(2u, detected_threads) - 1;

struct EcoLine {
  int id;
  string uci;
};

void classify_worker(const string &table, const vector<EcoLine> &eco_lines,
                     int start_id, int end_id, atomic<int> &total_updated) {
  try {
    sql::mysql::MySQL_Driver *driver = sql::mysql::get_mysql_driver_instance();
    unique_ptr<sql::Connection> conn(
        driver->connect(mysql_host, mysql_user, mysql_password));
    conn->setSchema(database);

    int last_id = start_id;

    while (last_id < end_id) {
      unique_ptr<sql::PreparedStatement> pstmt(
          conn->prepareStatement("SELECT id, moves_blob FROM " + table +
                                 " WHERE id >= ? AND id < ? AND ecoID IS NULL "
                                 "ORDER BY id ASC LIMIT ?"));
      pstmt->setInt(1, last_id);
      pstmt->setInt(2, end_id);
      pstmt->setInt(3, BATCH_SIZE);

      unique_ptr<sql::ResultSet> games(pstmt->executeQuery());

      vector<pair<int, int>> updates;

      while (games->next()) {
        int game_id = games->getInt("id");
        last_id = game_id;
        string moves_blob = games->getString("moves_blob");

        for (const auto &eco : eco_lines) {
          if (moves_blob.rfind(eco.uci, 0) == 0) { // starts with
            updates.emplace_back(eco.id, game_id);
            break;
          }
        }
      }

      if (updates.empty())
        break;

      unique_ptr<sql::PreparedStatement> update_stmt(conn->prepareStatement(
          "UPDATE " + table + " SET ecoID = ? WHERE id = ?"));

      for (const auto &upd : updates) {
        update_stmt->setInt(1, upd.first);
        update_stmt->setInt(2, upd.second);
        update_stmt->executeUpdate();
      }

      total_updated += updates.size();

      if (updates.size() < BATCH_SIZE)
        break;
    }
  } catch (sql::SQLException &e) {
    cerr << "[Thread " << this_thread::get_id() << "] SQL error: " << e.what()
         << endl;
  }
}

int main(int argc, char *argv[]) {
  string table = "all_games";
  if (argc > 1) {
    table = argv[1];
  }
  cout << "Using table: " << table << endl;

  try {
    sql::mysql::MySQL_Driver *driver = sql::mysql::get_mysql_driver_instance();
    unique_ptr<sql::Connection> conn(
        driver->connect(mysql_host, mysql_user, mysql_password));
    conn->setSchema(database);

    unique_ptr<sql::Statement> stmt(conn->createStatement());
    unique_ptr<sql::ResultSet> res(
        stmt->executeQuery("SELECT id, uci FROM eco WHERE uci IS NOT NULL "
                           "ORDER BY LENGTH(uci) DESC"));

    vector<EcoLine> eco_lines;
    while (res->next()) {
      eco_lines.push_back(EcoLine{res->getInt("id"), res->getString("uci")});
    }

    unique_ptr<sql::ResultSet> min_max(
        stmt->executeQuery("SELECT MIN(id) AS min_id, MAX(id) AS max_id FROM " +
                           table + " WHERE ecoID IS NULL"));
    int min_id = 0, max_id = 0;
    if (min_max->next()) {
      min_id = min_max->getInt("min_id");
      max_id = min_max->getInt("max_id");
    }

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

    cout << "Classification complete. Total updated: " << total_updated << endl;

  } catch (sql::SQLException &e) {
    cerr << "SQL error: " << e.what() << endl;
    return 1;
  }

  return 0;
}
