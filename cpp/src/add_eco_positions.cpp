#include <bit>
#include <iostream>
#include <string>
#include <vector>

#include "mysql_settings.hpp"
#include <mysql/mysql.h>

#include "chess-library/include/chess.hpp"

using namespace std;
using namespace chess;

const vector<string> SQUARES = {
    "a1", "b1", "c1", "d1", "e1", "f1", "g1", "h1", "a2", "b2", "c2",
    "d2", "e2", "f2", "g2", "h2", "a3", "b3", "c3", "d3", "e3", "f3",
    "g3", "h3", "a4", "b4", "c4", "d4", "e4", "f4", "g4", "h4", "a5",
    "b5", "c5", "d5", "e5", "f5", "g5", "h5", "a6", "b6", "c6", "d6",
    "e6", "f6", "g6", "h6", "a7", "b7", "c7", "d7", "e7", "f7", "g7",
    "h7", "a8", "b8", "c8", "d8", "e8", "f8", "g8", "h8"};

const vector<string> PIECES = {"p", "n", "b", "r", "q", "k", ""};

// in 20 moves max 4 pawns can be promoted, so max 6 pieces of each type and max
// 8 pawns
uint64_t count_hash(const Board &board) {
  uint64_t hash = 0;
  int shift = 0;

  auto add = [&](PieceType pt, Color c, int max_count) {
    int count = board.pieces(pt, c).count();

    uint64_t bits = (1ULL << count) - 1;

    hash |= bits << shift;

    shift += max_count;
  };

  add(PieceType::PAWN, Color::WHITE, 8);   // bits: 0-7
  add(PieceType::KNIGHT, Color::WHITE, 6); // bits: 8-13
  add(PieceType::BISHOP, Color::WHITE, 6); // bits: 14-19
  add(PieceType::ROOK, Color::WHITE, 6);   // bits: 20-25
  add(PieceType::QUEEN, Color::WHITE, 6);  // bits: 26-31

  add(PieceType::PAWN, Color::BLACK, 8);   // bits: 32-39
  add(PieceType::KNIGHT, Color::BLACK, 6); // bits: 40-45
  add(PieceType::BISHOP, Color::BLACK, 6); // bits: 46-51
  add(PieceType::ROOK, Color::BLACK, 6);   // bits: 52-57
  add(PieceType::QUEEN, Color::BLACK, 6);  // bits: 58-63

  return hash;
}

int main() {
  MYSQL *conn = mysql_init(nullptr);

  if (!mysql_real_connect(conn, mysql_host, mysql_user, mysql_password,
                          database, 0, nullptr, 0)) {
    cerr << mysql_error(conn) << "\n";
    return 1;
  }

  MYSQL_RES *result;

  if (mysql_query(conn, "SELECT id, uci FROM eco")) {
    cerr << mysql_error(conn) << "\n";
    return 1;
  }

  result = mysql_store_result(conn);

  MYSQL_ROW row;

  int inserted = 0;

  while ((row = mysql_fetch_row(result))) {
    const unsigned short eco_id = atoi(row[0]);

    const char *moves_cstr = row[1];
    if (!moves_cstr) {
      moves_cstr = "";
    }

    string moves(moves_cstr);

    Board board;
    char query[256];
    for (size_t i = 0; i + 1 < moves.size(); i += 2) {
      uint16_t packed = ((uint8_t)moves[i] << 8) | (uint8_t)moves[i + 1];

      int from = (packed >> 10) & 0x3f;
      int to = (packed >> 4) & 0x3f;
      int promotion = packed & 0x07;
      string uci = SQUARES[from] + SQUARES[to];

      if (!PIECES[promotion].empty()) {
        uci += PIECES[promotion];
      }

      Move move = chess::uci::uciToMove(board, uci);

      board.makeMove(move);

      const uint64_t zobrist = board.hash();

      snprintf(query, sizeof(query),
               "INSERT IGNORE INTO eco_positions "
               "(ecoId,zobrist) "
               "VALUES(%d,%lu)",
               eco_id, zobrist);

      if (mysql_query(conn, query)) {
        cerr << "Insert error: " << mysql_error(conn) << "\n";
      }
      inserted++;
    }
    const uint64_t chash = count_hash(board);
    snprintf(query, sizeof(query),
             "UPDATE eco "
             "SET count_hash = %lu "
             "WHERE id = %d",
             chash, eco_id);
    if (mysql_query(conn, query)) {
      cerr << "Update error: " << mysql_error(conn) << "\n";
    }
  }

  cout << "Inserted positions: " << inserted << "\n";

  mysql_free_result(result);
  mysql_close(conn);
}
