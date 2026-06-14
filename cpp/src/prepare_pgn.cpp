#include <algorithm>
#include <fstream>
#include <map>
#include <memory>
#include <regex>
#include <sstream>
#include <vector>

#include "chess-library/include/chess.hpp"

using namespace chess;
using namespace std;

class FilterVisitor : public pgn::Visitor {
public:
  FilterVisitor(ofstream &outFile) : outFile(outFile) {}

  void startPgn() override {
    board.setFen(constants::STARTPOS);
    is960 = false;
    isBotGame = false;
    whiteIsBot = false;
    blackIsBot = false;
    moves.clear();
    headers.clear();
    result = "*";
  }

  void header(string_view key, string_view value) override {
    headers[string(key)] = string(value);
    if (key == "FEN" && value != constants::STARTPOS) {
      is960 = true;
    }
    if (key == "WhiteTitle" && value == "BOT") {
      whiteIsBot = true;
    }
    if (key == "BlackTitle" && value == "BOT") {
      blackIsBot = true;
    }
    if (key == "Result") {
      result = string(value);
    }
  }

  void startMoves() override {}

  void move(string_view move, string_view comment) override {
    moves.push_back(string(move));
  }

  void endPgn() override {
    isBotGame = whiteIsBot && blackIsBot;
    if (!is960 && !isBotGame && extractYear(headers["Date"]) > 1899) {
      for (const auto &[key, val] : headers) {
        outFile << "[" << key << " \"" << val << "\"]\n";
      }
      outFile << "\n";

      for (size_t i = 0; i < moves.size(); ++i) {
        if (i % 2 == 0) {
          outFile << (i / 2) + 1 << ". " << moves[i] << " ";
        } else {
          outFile << moves[i] << " ";
        }
        if (i % 50 == 49) {
          outFile << "\n";
        }
      }
      outFile << result << "\n\n";
    }
  }

private:
  ofstream &outFile;
  Board board;
  bool is960 = false;
  bool isBotGame = false;
  bool whiteIsBot = false;
  bool blackIsBot = false;
  vector<string> moves;
  map<string, string> headers;
  string result;

  int extractYear(string_view value) {
    regex dateRegex(R"((\d+)(?:[^\d]+(\d+)(?:[^\d]+(\d+))?)?)");
    smatch matches;
    string valueStr(value);

    if (regex_search(valueStr, matches, dateRegex)) {
      try {
        return stoi(matches[1].str());
      } catch (...) {
        return 0;
      }
    }
    return 0;
  }
};

pair<string, string> preprocessHeaderLine(const string &line) {
  static const regex headerRegex("\\[(\\w+)\\s+\"(.*)\"\\]");
  smatch matches;
  if (regex_match(line, matches, headerRegex)) {
    string key = matches[1].str();
    string value = matches[2].str();
    value.erase(remove(value.begin(), value.end(), '"'), value.end());
    value.erase(remove(value.begin(), value.end(), '\\'), value.end());
    return {key, value};
  }
  return {"", ""};
}

int main(int argc, char **argv) {
  string input_file;

  if (argc > 1) {
    input_file = argv[1];
  } else {
    cout << "Podaj nazwę pliku PGN: ";
    cin >> input_file;
    cout << endl;
  }

  ofstream outFile("clean.pgn");
  auto vis = make_unique<FilterVisitor>(outFile);

  ifstream file_stream(input_file);
  string line;

  stringstream cleaned_pgn;
  while (getline(file_stream, line)) {
    if (line.empty()) {
      cleaned_pgn << "\n";
      continue;
    }
    if (line[0] == '[') {
      auto [key, value] = preprocessHeaderLine(line);
      if (!key.empty()) {
        cleaned_pgn << "[" << key << " \"" << value << "\"]\n";
      } else {
        cleaned_pgn << line << "\n";
      }
    } else {
      cleaned_pgn << line << "\n";
    }
  }

  stringstream cleaned_stream(cleaned_pgn.str());
  try {
    pgn::StreamParser parser(cleaned_stream);
    const auto err = parser.readGames(*vis);

    if (err) {
      cerr << "PGN parse error: " << err.message() << '\n';
      return 1;
    }
  } catch (const std::exception &e) {
    cerr << "Exception: " << e.what() << '\n';
    return 1;
  }

  return 0;
}
