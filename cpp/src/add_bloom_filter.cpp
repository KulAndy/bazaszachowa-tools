#include <algorithm>
#include <atomic>
#include <cstring>
#include <iostream>
#include <memory>
#include <semaphore>
#include <string>
#include <thread>
#include <tuple>
#include <utility>
#include <vector>

#include "mysql_settings.hpp"
#include <mysql/mysql.h>

#include "chess-library/include/chess.hpp"

using namespace std;
using namespace chess;

constexpr int BATCH_SIZE = 1000;
constexpr char MAX_MOVES = 20;
constexpr char MAX_PLIES = MAX_MOVES * 2;

const int detected_threads = thread::hardware_concurrency();
const int N_THREADS = max(2, detected_threads) - 1;
std::counting_semaphore<3> db_semaphore(2);

const vector<string> SQUARES = {
    "a1", "b1", "c1", "d1", "e1", "f1", "g1", "h1", "a2", "b2", "c2",
    "d2", "e2", "f2", "g2", "h2", "a3", "b3", "c3", "d3", "e3", "f3",
    "g3", "h3", "a4", "b4", "c4", "d4", "e4", "f4", "g4", "h4", "a5",
    "b5", "c5", "d5", "e5", "f5", "g5", "h5", "a6", "b6", "c6", "d6",
    "e6", "f6", "g6", "h6", "a7", "b7", "c7", "d7", "e7", "f7", "g7",
    "h7", "a8", "b8", "c8", "d8", "e8", "f8", "g8", "h8"};

const vector<string> PIECES = {"p", "n", "b", "r", "q", "k", ""};

void classify_worker(const string &table, const int start_id, const int end_id,
                     atomic<int> &total_updated) {
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

    snprintf(
        query, sizeof(query),
        "SELECT games.id, moves_blob, IFNULL(LENGTH(eco.uci), 0) FROM %s as "
        "games LEFT "
        "JOIN eco ON eco.id = games.ecoID "
        "WHERE games.id >= %d AND games.id < %d and "
        "bitboardsID IS NULL ORDER BY games.id ASC LIMIT %d",
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

    vector<tuple<int, Bitboard, Bitboard, Bitboard>> updates;
    MYSQL_ROW row;

    while ((row = mysql_fetch_row(result))) {

      if (!row[0]) {
        continue;
      }

      int game_id = atoi(row[0]);
      last_id = game_id;

      const char *moves_cstr = row[1];
      if (!moves_cstr) {
        moves_cstr = "";
      }
      size_t eco_length = stoull(row[2]);

      string movesData(moves_cstr);

      uint64_t start_pawns_moves = 0;
      Bitboard pawn_bitmap;
      Bitboard knight_bitmap;
      Bitboard bishop_bitmap;
      Bitboard rook_bitmap;
      Bitboard queen_bitmap;
      Bitboard king_bitmap;

      Board board;

      auto set_bit = [&](Bitboard &bitmap, const chess::Move move, bool clear) {
        if (clear) {
          pawn_bitmap.clear(move.to().index());
          knight_bitmap.clear(move.to().index());
          bishop_bitmap.clear(move.to().index());
          rook_bitmap.clear(move.to().index());
          queen_bitmap.clear(move.to().index());
          king_bitmap.clear(move.to().index());

          bitmap.clear(move.from().index());
        }
        bitmap.set(move.to().index());
      };

      size_t maxBytes = min(movesData.size(), size_t(MAX_PLIES));
      for (size_t i = 0; i + 1 < maxBytes; i += 2) {
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
        Piece movedPiece = board.at(move.from());
        PieceType pieceType = movedPiece.type();

        Square destination = move.to();

        board.makeMove(move);

        if (pieceType == PieceType::PAWN) {
          if (move.typeOf() == Move::PROMOTION) {
            pieceType = move.promotionType();
          } else {
            set_bit(pawn_bitmap, move, i < eco_length + 1);
            if (i < 10) {
              start_pawns_moves |= destination.index();
            }
          }
        }
        if (pieceType == PieceType::ROOK) {
          set_bit(rook_bitmap, move, i < eco_length + 1);
        } else if (pieceType == PieceType::KNIGHT) {
          set_bit(knight_bitmap, move, i < eco_length + 1);
        } else if (pieceType == PieceType::BISHOP) {
          set_bit(bishop_bitmap, move, i < eco_length + 1);
        } else if (pieceType == PieceType::QUEEN) {
          set_bit(queen_bitmap, move, i < eco_length + 1);
        } else if (pieceType == PieceType::KING) {
          if (move.typeOf() == Move::CASTLING) {
            switch (destination.index()) {
            case Square(Square::underlying::SQ_A1).index():
            case Square(Square::underlying::SQ_A8).index():
              destination++;
              destination++;
              rook_bitmap.set(destination.index() + 1);
              break;
            case Square(Square::underlying::SQ_H1).index():
            case Square(Square::underlying::SQ_H8).index():
              destination--;
              rook_bitmap.set(destination.index() - 1);
              break;
            }
            king_bitmap.set(destination.index());
          } else {
            set_bit(king_bitmap, move, i < eco_length + 1);
          }
        }
      }
      Bitboard bitmap1 =
          Bitboard((pawn_bitmap.getBits() << 8) | (start_pawns_moves & 0xFF));
      Bitboard bitmap2 = bishop_bitmap | rook_bitmap;
      Bitboard bitmap3 = knight_bitmap | king_bitmap | queen_bitmap;
      updates.emplace_back(make_tuple(game_id, bitmap1, bitmap2, bitmap3));
    }

    auto appendBitmapBytes = [](std::string &sql, uint64_t bits) {
      for (int i = 0; i < 8; ++i) {
        if (i > 0)
          sql += ',';

        sql += std::to_string((bits >> (i * 8)) & 0xFF);
      }
    };

    db_semaphore.acquire();
    for (const auto &upd : updates) {
      std::string query = "INSERT INTO bitboards("
                          "bitmap1_r1,bitmap1_r2,bitmap1_r3,bitmap1_r4,"
                          "bitmap1_r5,bitmap1_r6,bitmap1_r7,bitmap1_r8,"
                          "bitmap2_r1,bitmap2_r2,bitmap2_r3,bitmap2_r4,"
                          "bitmap2_r5,bitmap2_r6,bitmap2_r7,bitmap2_r8,"
                          "bitmap3_r1,bitmap3_r2,bitmap3_r3,bitmap3_r4,"
                          "bitmap3_r5,bitmap3_r6,bitmap3_r7,bitmap3_r8)"
                          " VALUES(";
      int game_id = get<0>(upd);
      Bitboard bitmap1 = get<1>(upd);
      Bitboard bitmap2 = get<2>(upd);
      Bitboard bitmap3 = get<3>(upd);
      appendBitmapBytes(query, bitmap1.getBits());
      query += ",";
      appendBitmapBytes(query, bitmap2.getBits());
      query += ",";
      appendBitmapBytes(query, bitmap3.getBits());
      query += ") ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)";

      if (mysql_query(conn, query.c_str())) {
        cerr << "Insert error: " << mysql_error(conn) << "\n";
      }
      uint64_t bitboardsID = mysql_insert_id(conn);
      query = "UPDATE `" + table +
              "` SET bitboardsID=" + std::to_string(bitboardsID) +
              " WHERE id=" + std::to_string(game_id);

      if (mysql_query(conn, query.c_str())) {
        cerr << "Update error: " << mysql_error(conn) << "\n";
      }
    }
    db_semaphore.release();

    total_updated += updates.size();

    if (updates.size() < BATCH_SIZE)
      break;

    mysql_free_result(result);
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

  char minmax[256];
  snprintf(minmax, sizeof(minmax),
           "SELECT MIN(id), MAX(id) FROM %s WHERE bitboardsID IS NULL",
           table.c_str());

  if (mysql_query(conn, minmax)) {
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

  int min_id = 0, max_id = 0;

  MYSQL_ROW row;
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

    threads.emplace_back(classify_worker, table, start_id, end_id + 1,
                         ref(total_updated));
  }

  for (auto &t : threads)
    t.join();

  cout << "Done. Updated: " << total_updated << "\n";

  return 0;
}
