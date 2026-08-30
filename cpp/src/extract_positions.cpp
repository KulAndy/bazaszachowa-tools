#include <array>
#include <chess-library/include/chess.hpp>
#include <cstddef>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <unordered_set>
#include <vector>

#include "MysqlConnection.hpp"
#include "RowMutex.hpp"
#include "mysql_settings.hpp"

using namespace std;
using mysql_is_null_t = std::remove_pointer_t<decltype(MYSQL_BIND{}.is_null)>;

const unsigned int detected_threads = thread::hardware_concurrency();
const unsigned int N_THREADS = max(2u, detected_threads) - 1;

const array<string, 64> SQUARES = {
    "a1", "b1", "c1", "d1", "e1", "f1", "g1", "h1", "a2", "b2", "c2",
    "d2", "e2", "f2", "g2", "h2", "a3", "b3", "c3", "d3", "e3", "f3",
    "g3", "h3", "a4", "b4", "c4", "d4", "e4", "f4", "g4", "h4", "a5",
    "b5", "c5", "d5", "e5", "f5", "g5", "h5", "a6", "b6", "c6", "d6",
    "e6", "f6", "g6", "h6", "a7", "b7", "c7", "d7", "e7", "f7", "g7",
    "h7", "a8", "b8", "c8", "d8", "e8", "f8", "g8", "h8"};

const array<string, 7> PIECES = {"p", "n", "b", "r", "q", "k", ""};

struct GameData {
  string id;
  string movesBlob;
};

void updateReverseIndex(int gameId, const string &table, uint64_t hash) {
  mysql::Connection conn(mysql_host, mysql_user, mysql_password, database);

  const std::string selectSql = "SELECT UNCOMPRESS(`reverse_index`) "
                                "FROM `positions` "
                                "WHERE `games_table` = ? AND `zobrist` = ?";

  auto selectStmt = conn.statement(selectSql);

  array<MYSQL_BIND, 2> selectParams{};

  selectParams[0].buffer_type = MYSQL_TYPE_STRING;
  selectParams[0].buffer = const_cast<char *>(table.data());
  selectParams[0].buffer_length = static_cast<unsigned long>(table.size());

  selectParams[1].buffer_type = MYSQL_TYPE_LONGLONG;
  selectParams[1].buffer = &hash;

  selectStmt.bindParam(selectParams.data());
  selectStmt.execute();

  auto metadata = selectStmt.resultMetadata();

  mysql::BoundResult<1> result;
  selectStmt.bindResult(result.data());

  std::string reverseIndex;

  if (selectStmt.fetch() == 0) {
    reverseIndex = result.get(0);
  }
  selectStmt.freeResult();

  if (gameId < 0) {
    throw std::invalid_argument("Invalid negative game ID");
  }

  const size_t byteIndex = static_cast<size_t>(gameId) / 8;

  const unsigned int bitIndex = static_cast<unsigned int>(gameId) % 8;

  if (reverseIndex.size() <= byteIndex) {
    reverseIndex.resize(byteIndex + 1, '\0');
  }

  reverseIndex[byteIndex] |= static_cast<char>(1u << bitIndex);

  const std::string insertSql = "INSERT INTO `positions` "
                                "(`zobrist`, `games_table`, `reverse_index`) "
                                "VALUES (?, ?, COMPRESS(?)) "
                                "ON DUPLICATE KEY UPDATE "
                                "`reverse_index` = COMPRESS(?)";

  auto insertStmt = conn.statement(insertSql);

  array<MYSQL_BIND, 4> params{};

  params[0].buffer_type = MYSQL_TYPE_LONGLONG;
  params[0].buffer = &hash;

  params[1].buffer_type = MYSQL_TYPE_STRING;
  params[1].buffer = const_cast<char *>(table.data());
  params[1].buffer_length = static_cast<unsigned long>(table.size());

  params[2].buffer_type = MYSQL_TYPE_BLOB;
  params[2].buffer = reverseIndex.data();
  params[2].buffer_length = static_cast<unsigned long>(reverseIndex.size());

  params[3].buffer_type = MYSQL_TYPE_BLOB;
  params[3].buffer = reverseIndex.data();
  params[3].buffer_length = static_cast<unsigned long>(reverseIndex.size());

  insertStmt.bindParam(params.data());
  insertStmt.execute();
}

void insertHashes(int gameId, const string &table,
                  const unordered_set<uint64_t> &hashes) {
  static RowMutexes<uint64_t> rowMutexes;

  for (uint64_t hash : hashes) {
    auto mutex = rowMutexes.get(hash);

    std::lock_guard<std::mutex> lock(*mutex);

    updateReverseIndex(gameId, table, hash);
  }
}

void processGame(GameData &&game, const string &table) {
  mysql::Connection conn(mysql_host, mysql_user, mysql_password, database);

  const int gameId = std::stoi(game.id);
  unordered_set<uint64_t> hashes;
  chess::Board board;
  const string &movesData = game.movesBlob;
  uint64_t hash = board.zobrist();

  for (size_t i = 0; i + 1 < movesData.size(); i += 2) {
    std::byte byte1 = static_cast<std::byte>(movesData[i]);
    std::byte byte2 = static_cast<std::byte>(movesData[i + 1]);
    uint16_t packed =
        (static_cast<uint16_t>(byte1) << 8) | static_cast<uint16_t>(byte2);

    int from = (packed >> 10) & 0x3f;
    int to = (packed >> 4) & 0x3f;
    int promotion = packed & 0x07;

    string uci = SQUARES[from] + SQUARES[to];

    if (!PIECES[promotion].empty()) {
      uci += PIECES[promotion];
    }

    chess::Move move = chess::uci::uciToMove(board, uci);
    board.makeMove(move);
    hash = board.zobrist();
    hashes.insert(hash);
  }

  insertHashes(gameId, table, hashes);
  const std::string updateSql = "UPDATE `" + table +
                                "` "
                                "SET `scanned` = 1 "
                                "WHERE `id` = ?";

  auto updateStmt = conn.statement(updateSql);

  array<MYSQL_BIND, 1> params{};

  params[0].buffer_type = MYSQL_TYPE_LONG;
  params[0].buffer = const_cast<int *>(&gameId);

  updateStmt.bindParam(params.data());
  updateStmt.execute();
}

void processYear(const string &table, const string &year) {
  try {
    mysql::Connection conn(mysql_host, mysql_user, mysql_password, database);

    const int limit = 1000;

    while (true) {
      const string query = "SELECT `id`, `moves_blob` "
                           "FROM `" +
                           table +
                           "` "
                           "WHERE `Year` = ? "
                           "AND `scanned` = 0 "
                           "LIMIT " +
                           to_string(limit);

      auto stmt = conn.statement(query);

      array<MYSQL_BIND, 1> params{};

      string yearValue = year;

      params[0].buffer_type = MYSQL_TYPE_STRING;
      params[0].buffer = yearValue.data();
      params[0].buffer_length = static_cast<unsigned long>(yearValue.size());

      stmt.bindParam(params.data());
      stmt.execute();

      auto metadata = stmt.resultMetadata();

      mysql::BoundResult<2> result;
      stmt.bindResult(result.data());

      vector<GameData> games;
      games.reserve(limit);

      while (stmt.fetch() == 0) {
        GameData game;

        game.id = result.get(0);
        game.movesBlob = result.get(1);

        games.emplace_back(std::move(game));
      }

      if (games.empty()) {
        break;
      }

      for (auto &game : games) {
        processGame(std::move(game), table);
      }
    }

  } catch (const exception &e) {
    cerr << "Error processing year " << year << ": " << e.what() << '\n';
  }
}

int main(int argc, const char *argv[]) {
  unordered_set<string> allowed_tables{"all_games", "poland_games"};
  string table = "all_games";

  if (argc > 1) {
    table = argv[1];
  }

  if (!allowed_tables.contains(table)) {
    throw std::invalid_argument("Invalid table name");
  }

  cout << "Using table: " << table << '\n';

  try {
    mysql::Connection conn(mysql_host, mysql_user, mysql_password, database);

    string query = "SELECT DISTINCT `Year` "
                   "FROM `" +
                   table +
                   "` "
                   "WHERE `Year` IS NOT NULL";

    auto result = conn.queryResult(query);

    set<string, less<>> years;

    while (auto row = result.fetchRow()) {
      if (row[0]) {
        years.emplace(row[0]);
      }
    }

    vector<thread> workers;
    workers.reserve(N_THREADS);

    for (const auto &year : years) {
      if (workers.size() >= N_THREADS) {
        for (auto &t : workers) {
          if (t.joinable()) {
            t.join();
          }
        }

        workers.clear();
      }

      workers.emplace_back(processYear, cref(table), cref(year));
    }

    for (auto &t : workers) {
      if (t.joinable()) {
        t.join();
      }
    }

    cout << "All games processed.\n";

  } catch (const exception &e) {
    cerr << "MySQL error: " << e.what() << '\n';

    return 1;
  }

  return 0;
}
