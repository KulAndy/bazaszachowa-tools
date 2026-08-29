#include <array>
#include <chess-library/include/chess.hpp>
#include <cstddef>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include "MysqlConnection.hpp"
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
  string event;
  string site;
  string date;
  string round;
  string white;
  string black;
  string result;
  string whiteElo;
  string blackElo;
  string eco;
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
    cerr << "Failed to open output file for year " << year << '\n';
    return;
  }

  for (auto &game : games) {
    processGame(std::move(game), output);
  }

  output.close();
}

void processYear(const string &table, const string &year) {
  try {
    mysql::Connection conn(mysql_host, mysql_user, mysql_password, database);

    string query = "SELECT chess_events.name, sites.site, `Year`, "
                   "`Month`, `Day`, `Round`, "
                   "p1.fullname, p2.fullname, `Result`, "
                   "`WhiteElo`, `BlackElo`, eco.ECO, `moves_blob` "
                   "FROM `" +
                   table +
                   "` "
                   "LEFT JOIN chess_events "
                   "ON eventID = chess_events.id "
                   "LEFT JOIN sites "
                   "ON siteID = sites.id "
                   "LEFT JOIN players AS p1 "
                   "ON WhiteID = p1.id "
                   "LEFT JOIN players AS p2 "
                   "ON BlackID = p2.id "
                   "LEFT JOIN eco "
                   "ON ecoID = eco.id "
                   "WHERE `Year` = ? "
                   "LIMIT ? OFFSET ?";

    auto stmt = conn.statement(query);

    array<MYSQL_BIND, 3> params{};

    string yearValue = year;
    int limit = 1000;
    int offset = 0;

    params[0].buffer_type = MYSQL_TYPE_STRING;
    params[0].buffer = yearValue.data();
    params[0].buffer_length = yearValue.size();

    params[1].buffer_type = MYSQL_TYPE_LONG;
    params[1].buffer = &limit;

    params[2].buffer_type = MYSQL_TYPE_LONG;
    params[2].buffer = &offset;

    stmt.bindParam(params.data());

    bool moreRows = true;

    while (moreRows) {
      moreRows = false;

      stmt.execute();

      auto metadata = stmt.resultMetadata();

      mysql::BoundResult<13> result;
      stmt.bindResult(result.data());

      vector<GameData> games;
      games.reserve(limit);

      while (stmt.fetch() == 0) {
        moreRows = true;

        GameData game;

        game.event = result.get(0);
        game.site = result.get(1);

        string yearLocal = result.get(2);
        string month = result.get(3);
        string day = result.get(4);

        game.date = buildDate(yearLocal, month, day);

        game.round = result.get(5);
        game.white = result.get(6);
        game.black = result.get(7);
        game.result = result.get(8);
        game.whiteElo = result.get(9);
        game.blackElo = result.get(10);
        game.eco = result.get(11);
        game.movesBlob = result.get(12);

        games.push_back(std::move(game));
      }

      if (!games.empty()) {
        processBatch(std::move(games), year);
      }

      offset += limit;
    }

  } catch (const exception &e) {
    cerr << "Error processing year " << year << ": " << e.what() << '\n';
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
