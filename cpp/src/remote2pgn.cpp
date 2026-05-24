#include "chess-library/include/chess.hpp"
#include "mysql_settings.hpp"
#include <condition_variable>
#include <cppconn/prepared_statement.h>
#include <cppconn/resultset.h>
#include <cppconn/statement.h>
#include <fstream>
#include <iostream>
#include <memory>
#include <mutex>
#include <mysql_connection.h>
#include <mysql_driver.h>
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
  try {
    sql::mysql::MySQL_Driver *driver = sql::mysql::get_mysql_driver_instance();
    unique_ptr<sql::Connection> con(
        driver->connect(mysql_host, mysql_user, mysql_password));
    con->setSchema(database);

    const int batchSize = 1000;
    int offset = 0;
    bool moreRows = true;

    while (moreRows) {
      try {
        unique_ptr<sql::PreparedStatement> pstmt(con->prepareStatement(
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
            "WHERE `Year` = ? LIMIT ? OFFSET ?"));

        pstmt->setString(1, year);
        pstmt->setInt(2, batchSize);
        pstmt->setInt(3, offset);

        unique_ptr<sql::ResultSet> res(pstmt->executeQuery());

        vector<GameData> batchGames;
        moreRows = false;

        while (res->next()) {
          moreRows = true;
          GameData game;
          game.event = res->isNull(1) ? "" : res->getString(1);
          game.site = res->isNull(2) ? "" : res->getString(2);
          string year = res->isNull(3) ? "" : res->getString(3);
          string month = res->isNull(4) ? "" : res->getString(4);
          string day = res->isNull(5) ? "" : res->getString(5);
          game.date = buildDate(year, month, day);
          game.round = res->isNull(6) ? "" : res->getString(6);
          game.white = res->isNull(7) ? "" : res->getString(7);
          game.black = res->isNull(8) ? "" : res->getString(8);
          game.result = res->isNull(9) ? "" : res->getString(9);
          game.whiteElo = res->isNull(10) ? "" : res->getString(10);
          game.blackElo = res->isNull(11) ? "" : res->getString(11);
          game.eco = res->isNull(12) ? "" : res->getString(12);
          game.movesBlob = res->isNull(13) ? "" : res->getString(13);
          batchGames.push_back(move(game));
        }

        if (!batchGames.empty()) {
          processBatch(move(batchGames), year);
        }

        offset += batchSize;
      } catch (const sql::SQLException &e) {
        if (string(e.what()).find("needs to be re-prepared") != string::npos) {
          cerr << "Retrying to prepare statement for year " << year << ": "
               << e.what() << endl;
          continue;
        } else {
          cerr << "SQL Error in thread for year " << year << ": " << e.what()
               << endl;
          break;
        }
      } catch (const exception &e) {
        cerr << "Error in thread for year " << year << ": " << e.what() << endl;
        break;
      }
    }
  } catch (const sql::SQLException &e) {
    cerr << "SQL Error in thread for year " << year << ": " << e.what() << endl;
  } catch (const exception &e) {
    cerr << "Error in thread for year " << year << ": " << e.what() << endl;
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
    unique_ptr<sql::Connection> con(
        driver->connect(mysql_host, mysql_user, mysql_password));
    con->setSchema(database);

    unique_ptr<sql::Statement> stmt(con->createStatement());
    unique_ptr<sql::ResultSet> yearsRes(
        stmt->executeQuery("SELECT DISTINCT `Year` FROM `" + table +
                           "` WHERE `Year` IS NOT NULL"));

    set<string> years;
    while (yearsRes->next()) {
      years.insert(yearsRes->getString(1));
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
      workers.emplace_back(processYear, table, year);
    }

    for (auto &t : workers) {
      if (t.joinable()) {
        t.join();
      }
    }

    cout << "All games processed." << endl;
  } catch (const sql::SQLException &e) {
    cerr << "SQL Error: " << e.what() << endl;
    return 1;
  } catch (const exception &e) {
    cerr << "Error: " << e.what() << endl;
    return 1;
  }

  return 0;
}
