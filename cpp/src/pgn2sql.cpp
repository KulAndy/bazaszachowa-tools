#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <optional>
#include <regex>

#include "chess-library/include/chess.hpp"

using namespace chess;
using namespace std;

const bool validateDate(string_view date) {
  if (date.size() < 4) {
    return false;
  }

  for (size_t i = 0; i < 4; ++i) {
    if (!std::isdigit(date[i])) {
      return false;
    }
  }

  return true;
}

class MyVisitor : public pgn::Visitor {
public:
public:
  MyVisitor(std::ofstream &outFile, const std::string &tableName)
      : outFile(outFile), tableName(tableName) {
    cout << endl;
  }

  virtual ~MyVisitor() {}

  void startPgn() {
    board.setFen(constants::STARTPOS);
    movesStream.str("");
    movesStream.clear();
  }

  void header(std::string_view key, std::string_view value) {
    if (key == "Event") {
      event = value;
    } else if (key == "Site") {
      site = value;
    } else if (key == "Round") {
      round = value;
    } else if (key == "White") {
      white = value;
    } else if (key == "Black") {
      black = value;
    } else if (key == "WhiteElo") {
      whiteElo = stoi(string(value));
    } else if (key == "BlackElo") {
      blackElo = stoi(string(value));
    } else if (key == "Result") {
      result = value;
    } else if (key == "Date") {
      parseDateValue(value);
    } else if (key == "EventDate") {
      if (validateDate(value) && (!year.has_value() || year.value() == 1899)) {
        parseDateValue(value);
      }
    } else if (key == "UTCDate") {
      if (validateDate(value) && (!year.has_value() || year.value() == 1899)) {
        parseDateValue(value);
      }
    }
  }

  void startMoves() {}

  void move(string_view move, string_view comment) {
    try {
      const Move m = uci::parseSan(board, move);
      const string moveUci = uci::moveToUci(m);

      int src = m.from().index();
      int dest = m.to().index();

      if (m.typeOf() == Move::CASTLING) {
        switch (dest) {
        case Square(Square::underlying::SQ_A1).index():
        case Square(Square::underlying::SQ_A8).index():
          dest += 2;
          break;
        case Square(Square::underlying::SQ_H1).index():
        case Square(Square::underlying::SQ_H8).index():
          dest--;
          break;
        }
      }

      PieceType piece = PieceType::NONE;

      if (move.find("=") != string::npos) {
        piece = m.promotionType();
      }

      uint16_t packed = (static_cast<uint16_t>(src) << 10) |
                        (static_cast<uint16_t>(dest) << 4) |
                        (static_cast<uint16_t>(piece) & 0x07);

      movesStream << static_cast<char>((packed >> 8) & 0xFF)
                  << static_cast<char>(packed & 0xFF);
      board.makeMove(m);
    } catch (exception &e) {
      cerr << "Error in move processing: " << e.what() << endl;
    }
  }

  void endPgn() {
    outFile << "insert ignore into " << tableName
            << " (moves_blob,Event,Site,Year,Month,Day,Round,White,Black,"
               "Result,WhiteElo,BlackElo) values("
            << "0x";
    for (unsigned char c : movesStream.str()) {
      outFile << std::hex << std::setw(2) << std::setfill('0')
              << static_cast<int>(c);
    }
    outFile << std::dec;

    outFile << "," << "\"" << event << "\"" << "," << "\"" << site << "\""
            << ",";
    if (year.has_value()) {
      outFile << year.value();
    } else {
      outFile << "null";
    }

    outFile << ",";

    if (month.has_value()) {
      outFile << month.value();
    } else {
      outFile << "null";
    }

    outFile << ",";

    if (day.has_value()) {
      outFile << day.value();
    } else {
      outFile << "null";
    }

    outFile << "," << "\"" << round << "\"" << "," << "\"" << white << "\""
            << "," << "\"" << black << "\"" << "," << "\"" << result << "\""
            << ",";

    if (whiteElo.has_value()) {
      outFile << whiteElo.value();
    } else {
      outFile << "NULL";
    }

    outFile << ",";

    if (blackElo.has_value()) {
      outFile << blackElo.value();
    } else {
      outFile << "NULL";
    }

    outFile << ");\n";

    cout << "\rPrzetworzono " << ++counter << " partii";
  }

protected:
  std::ofstream &outFile;
  std::string tableName;
  Board board;
  string event = "?";
  string site = "?";
  optional<int> year;
  optional<int> month;
  optional<int> day;
  string round = "?";
  string white = "N, N";
  string black = "N, N";
  optional<int> whiteElo;
  optional<int> blackElo;
  string result = "*";
  ostringstream movesStream;
  int counter = 0;

  void parseDateValue(string_view value) {
    std::regex dateRegex(R"((\d+)(?:[^\d]+(\d+)(?:[^\d]+(\d+))?)?)");
    std::smatch matches;
    std::string valueStr(value);

    if (std::regex_search(valueStr, matches, dateRegex)) {
      try {
        year = std::stoi(matches[1].str());
        if (matches.size() > 2 && !matches[2].str().empty()) {
          month = std::stoi(matches[2].str());
        }

        if (matches.size() > 3 && !matches[3].str().empty()) {
          day = std::stoi(matches[3].str());
        }
      } catch (...) {
      }
    }
  }
};

int main(int argc, char **argv) {
  string input_file, target_table;

  if (argc > 1) {
    input_file = argv[1];
  } else {
    cout << "Podaj nazwę pliku PGN: ";
    cin >> input_file;
    cout << endl;
  }

  if (argc > 2) {
    target_table = argv[2];
  } else {
    cout << "Podaj nazwę tabeli: ";
    cin >> target_table;
    cout << endl;
  }

  ofstream outFile("insert.sql");
  auto vis = make_unique<MyVisitor>(outFile, target_table);

  ifstream file_stream(input_file);
  pgn::StreamParser parser(file_stream);
  parser.readGames(*vis);
  cout << endl;

  return 0;
}
