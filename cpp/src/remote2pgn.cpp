#include "chess-library/include/chess.hpp"
#include "mysql_settings.hpp"
#include <condition_variable>
#include <fstream>
#include <iostream>
#include <memory>
#include <mutex>
#include <mysql/mysql.h>
#include <queue>
#include <set>
#include <sstream>
#include <thread>
#include <vector>

using namespace std;

const unsigned int detected_threads = thread::hardware_concurrency();
const unsigned int N_THREADS = max(2u, detected_threads) - 1;

const vector<string> SQUARES = {
    "a1", "b1", "c1", "d1", "e1", "f1", "g1", "h1", "a2", "b2", "c2",
    "d2", "e2", "f2", "g2", "h2", "a3", "b3", "c3", "d3", "e3", "f3",
    "g3", "h3", "a4", "b4", "c4", "d4", "e4", "f4", "g4", "h4", "a5",
    "b5", "c5", "d5", "e5", "f5", "g5", "h5", "a6", "b6", "c6", "d6",
    "e6", "f6", "g6", "h6", "a7", "b7", "c7", "d7", "e7", "f7", "g7",
    "h7", "a8", "b8", "c8", "d8", "e8", "f8", "g8", "h8"};

const vector<string> PIECES = {"p", "n", "b", "r", "q", "k", ""};

struct GameData {
  string event, site, date, round;
  string white, black, result, whiteElo, blackElo, eco;
  string movesBlob;
};

string buildDate(const string &year, const string &month, const string &day) {
  string date;
  date.reserve(10);
  date += year.empty() ? "????" : year;
  date += ".";
  date += month.empty() ? "??" : month;
  date += ".";
  date += day.empty() ? "??" : day;
  return date;
}

void writePgnHeaders(ostream &output,
                     const vector<pair<string, string>> &headers) {
  for (const auto &[key, value] : headers) {
    output << "[" << key << " \"" << value << "\"]\n";
  }
  output << "\n";
}

void processGame(GameData &&game, ostream &output) {
  vector<pair<string, string>> headers = {
      {"Event", game.event.empty() ? "?" : game.event},
      {"Site", game.site.empty() ? "?" : game.site},
      {"Date", game.date},
      {"Round", game.round.empty() ? "?" : game.round},
      {"White", game.white.empty() || game.white == "?" ? "N, N" : game.white},
      {"Black", game.black.empty() || game.black == "?" ? "N, N" : game.black},
      {"Result", game.result.empty() ? "*" : game.result},
      {"WhiteElo", game.whiteElo.empty() ? "?" : game.whiteElo},
      {"BlackElo", game.blackElo.empty() ? "?" : game.blackElo},
      {"ECO", game.eco.empty() ? "?" : game.eco}};

  writePgnHeaders(output, headers);

  chess::Board board;
  istringstream movesBlob(game.movesBlob);
  string movesData = movesBlob.str();
  size_t counter = 2;

  for (size_t i = 0; i + 1 < movesData.size(); i += 2) {
    uint16_t packed = (static_cast<uint8_t>(movesData[i]) << 8) |
                      static_cast<uint8_t>(movesData[i + 1]);
    int from = (packed >> 10) & 0x3f;
    int to = (packed >> 4) & 0x3f;
    int promotion = packed & 0x07;
    string uci = SQUARES[from] + SQUARES[to];

    if (!PIECES[promotion].empty()) {
      uci += PIECES[promotion];
    }

    chess::Move move = chess::uci::uciToMove(board, uci);
    if (counter % 2 == 0) {
      output << (counter / 2) << ". ";
    }
    string san = chess::uci::moveToSan(board, move);
    board.makeMove(move);
    output << san << " ";
    counter++;
  }

  output << (game.result.empty() ? "*" : game.result) << "\n\n";
}

void processBatch(vector<GameData> &&games, const string &year) {
  string filename = "games" + year + ".pgn";
  ofstream output(filename, ios::app);
  if (!output.is_open()) {
    cerr << "Failed to open output file for year " << year << endl;
    return;
  }

  for (auto &game : games) {
    processGame(move(game), output);
  }

  output.close();
}

void processYear(const string table, const string &year) {
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

  string query =
      "SELECT chess_events.name, sites.site, `Year`, `Month`, `Day`, "
      "`Round`, "
      "p1.fullname, p2.fullname, `Result`, `WhiteElo`, `BlackElo`, "
      "eco.ECO, `moves_blob` "
      "FROM `" +
      table +
      "` "
      "LEFT JOIN chess_events ON eventID = chess_events.id "
      "LEFT JOIN sites ON siteID = sites.id "
      "LEFT JOIN players AS p1 ON WhiteID = p1.id "
      "LEFT JOIN players AS p2 ON BlackID = p2.id "
      "LEFT JOIN eco ON ecoID = eco.id "
      "WHERE `Year` = ? LIMIT ? OFFSET ?";

  MYSQL_STMT *stmt = mysql_stmt_init(conn);
  if (!stmt) {
    cerr << "mysql_stmt_init failed: " << mysql_error(conn) << "\n";
    mysql_close(conn);
    return;
  }

  if (mysql_stmt_prepare(stmt, query.c_str(), query.size())) {
    cerr << "mysql_stmt_prepare failed: " << mysql_stmt_error(stmt) << "\n";
    mysql_stmt_close(stmt);
    mysql_close(conn);
    return;
  }

  MYSQL_BIND param[3];
  memset(param, 0, sizeof(param));

  string year_str = year;
  param[0].buffer_type = MYSQL_TYPE_STRING;
  param[0].buffer = (void *)year_str.c_str();
  param[0].buffer_length = year_str.size();
  param[0].is_null = 0;
  param[0].length = &param[0].buffer_length;

  int batchSize = 1000;
  param[1].buffer_type = MYSQL_TYPE_LONG;
  param[1].buffer = (void *)&batchSize;
  param[1].is_null = 0;
  param[1].length = nullptr;

  int offset = 0;
  param[2].buffer_type = MYSQL_TYPE_LONG;
  param[2].buffer = (void *)&offset;
  param[2].is_null = 0;
  param[2].length = nullptr;

  if (mysql_stmt_bind_param(stmt, param)) {
    cerr << "mysql_stmt_bind_param failed: " << mysql_stmt_error(stmt) << "\n";
    mysql_stmt_close(stmt);
    mysql_close(conn);
    return;
  }

  bool moreRows = true;
  while (moreRows) {
    moreRows = false;

    param[2].buffer = (void *)&offset;

    if (mysql_stmt_execute(stmt)) {
      cerr << "mysql_stmt_execute failed: " << mysql_stmt_error(stmt) << "\n";
      break;
    }

    MYSQL_RES *result = mysql_stmt_result_metadata(stmt);
    if (!result) {
      cerr << "mysql_stmt_result_metadata failed: " << mysql_stmt_error(stmt)
           << "\n";
      break;
    }

    MYSQL_BIND bind[13];
    memset(bind, 0, sizeof(bind));

    char *buffers[13];
    unsigned long lengths[13];
    int num_fields = mysql_num_fields(result);

    for (int i = 0; i < num_fields; ++i) {
      buffers[i] = new char[1024];
      lengths[i] = 1024;
      bind[i].buffer_type = MYSQL_TYPE_STRING;
      bind[i].buffer = buffers[i];
      bind[i].buffer_length = 1024;
      bind[i].length = &lengths[i];
      bind[i].is_null = new bool;
      *(bind[i].is_null) = 0;
    }

    if (mysql_stmt_bind_result(stmt, bind)) {
      cerr << "mysql_stmt_bind_result failed: " << mysql_stmt_error(stmt)
           << "\n";
      mysql_free_result(result);
      for (int i = 0; i < num_fields; ++i) {
        delete[] buffers[i];
        delete bind[i].is_null;
      }
      break;
    }

    vector<GameData> batchGames;
    while (!mysql_stmt_fetch(stmt)) {
      moreRows = true;
      GameData game;
      game.event = bind[0].is_null && *(bind[0].is_null)
                       ? ""
                       : string(buffers[0], lengths[0]);
      game.site = bind[1].is_null && *(bind[1].is_null)
                      ? ""
                      : string(buffers[1], lengths[1]);
      string year = bind[2].is_null && *(bind[2].is_null)
                        ? ""
                        : string(buffers[2], lengths[2]);
      string month = bind[3].is_null && *(bind[3].is_null)
                         ? ""
                         : string(buffers[3], lengths[3]);
      string day = bind[4].is_null && *(bind[4].is_null)
                       ? ""
                       : string(buffers[4], lengths[4]);
      game.date = buildDate(year, month, day);
      game.round = bind[5].is_null && *(bind[5].is_null)
                       ? ""
                       : string(buffers[5], lengths[5]);
      game.white = bind[6].is_null && *(bind[6].is_null)
                       ? ""
                       : string(buffers[6], lengths[6]);
      game.black = bind[7].is_null && *(bind[7].is_null)
                       ? ""
                       : string(buffers[7], lengths[7]);
      game.result = bind[8].is_null && *(bind[8].is_null)
                        ? ""
                        : string(buffers[8], lengths[8]);
      game.whiteElo = bind[9].is_null && *(bind[9].is_null)
                          ? ""
                          : string(buffers[9], lengths[9]);
      game.blackElo = bind[10].is_null && *(bind[10].is_null)
                          ? ""
                          : string(buffers[10], lengths[10]);
      game.eco = bind[11].is_null && *(bind[11].is_null)
                     ? ""
                     : string(buffers[11], lengths[11]);
      game.movesBlob = bind[12].is_null && *(bind[12].is_null)
                           ? ""
                           : string(buffers[12], lengths[12]);
      batchGames.push_back(move(game));
    }

    mysql_free_result(result);
    for (int i = 0; i < num_fields; ++i) {
      delete[] buffers[i];
      delete bind[i].is_null;
    }

    if (!batchGames.empty()) {
      processBatch(move(batchGames), year);
    }

    offset += batchSize;
  }

  mysql_stmt_close(stmt);
  mysql_close(conn);
}
int main(int argc, char *argv[]) {
  string table = "all_games";
  if (argc > 1) {
    table = argv[1];
  }
  cout << "Using table: " << table << endl;

  MYSQL *conn = mysql_init(nullptr);
  if (!conn) {
    cerr << "mysql_init failed\n";
    return 1;
  }

  if (!mysql_real_connect(conn, mysql_host, mysql_user, mysql_password,
                          database, 0, nullptr, 0)) {
    cerr << "Connection error: " << mysql_error(conn) << "\n";
    mysql_close(conn);
    return 1;
  }

  string query =
      "SELECT DISTINCT `Year` FROM `" + table + "` WHERE `Year` IS NOT NULL";
  if (mysql_query(conn, query.c_str())) {
    cerr << "Query error: " << mysql_error(conn) << "\n";
    mysql_close(conn);
    return 1;
  }

  MYSQL_RES *result = mysql_store_result(conn);
  if (!result) {
    cerr << "Store result error: " << mysql_error(conn) << "\n";
    mysql_close(conn);
    return 1;
  }

  set<string> years;
  MYSQL_ROW row;
  while ((row = mysql_fetch_row(result))) {
    if (row[0]) {
      years.insert(row[0]);
    }
  }
  mysql_free_result(result);
  mysql_close(conn);

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
    workers.emplace_back(processYear, table, year);
  }

  for (auto &t : workers) {
    if (t.joinable()) {
      t.join();
    }
  }

  cout << "All games processed." << endl;
  return 0;
}
