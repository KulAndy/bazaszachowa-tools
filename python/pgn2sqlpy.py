import re
import sys
from os.path import exists

import chess
import chess.pgn


def validate_date(date_str):
    if len(date_str) < 4:
        return False
    for i in range(4):
        if not date_str[i].isdigit():
            return False
    return True


def parse_date(date_str):
    date_regex = r"(\d+)(?:[^\d]+(\d+)(?:[^\d]+(\d+))?)?"
    match = re.search(date_regex, date_str)
    if match:
        year = int(match.group(1))
        month = int(match.group(2)) if match.group(2) else None
        day = int(match.group(3)) if match.group(3) else None
        return year, month, day
    return None, None, None


def pack_move(src, dest, piece):
    return (src << 10) | (dest << 4) | (piece & 0x07)


def main():
    if len(sys.argv) >= 3:
        _, input_file, table_name = sys.argv[0:3]
    elif len(sys.argv) == 2:
        _, input_file = sys.argv
        table_name = input("Podaj nazwę tabeli do wstawienia danych: ")
        if table_name == "exit":
            sys.exit()
    else:
        input_file = input("Podaj ścieżkę do pliku PGN (lub 'exit'): ")
        if input_file == "exit":
            sys.exit()
        while not exists(input_file):
            input_file = input("Podaj jeszcze raz ścieżkę do pliku (lub 'exit'): ")
            if input_file == "exit":
                sys.exit()
        table_name = input("Podaj nazwę tabeli do wstawienia danych: ")
        if table_name == "exit":
            sys.exit()

    pgn_keys = [
        "Event", "Site", "Year", "Month", "Day", "Round",
        "White", "Black", "Result", "WhiteElo", "BlackElo"
    ]

    prefix = f"INSERT IGNORE INTO {table_name} (moves_blob, {', '.join(pgn_keys)}) VALUES (0x"

    with open("insert.sql", "w") as output, open("errors.log", "w") as error_log:
        counter = 0
        with open(input_file, errors="replace") as pgn_file:
            while True:
                game = chess.pgn.read_game(pgn_file)
                if game is None:
                    break

                game_data = {key: "null" for key in pgn_keys}
                game_data["Year"] = game_data["Month"] = game_data["Day"] = None
                moves_blob = bytearray()

                try:
                    for key in pgn_keys:
                        if key in game.headers:
                            value = game.headers[key]
                            if key in ("WhiteElo", "BlackElo"):
                                game_data[key] = int(value) if value != "?" else None
                            elif key in ("Event", "Site", "Round", "White", "Black", "Result"):
                                game_data[key] = value if value != "?" else "?"
                            elif key == "Date":
                                year, month, day = parse_date(value)
                                if year: game_data["Year"] = year
                                if month: game_data["Month"] = month
                                if day: game_data["Day"] = day

                    board = game.board()
                    for move in game.mainline_moves():
                        src = move.from_square
                        dest = move.to_square
                        piece = move.promotion if move.promotion else 0
                        packed = pack_move(src, dest, piece)
                        moves_blob.append((packed >> 8) & 0xFF)
                        moves_blob.append(packed & 0xFF)
                        board.push(move)

                    moves_hex = moves_blob.hex().upper()
                    values = []
                    for key in pgn_keys:
                        value = game_data[key]
                        if value is None:
                            values.append("NULL")
                        elif isinstance(value, str):
                            values.append(f'"{value}"')
                        else:
                            values.append(str(value))
                    sql = f"{prefix}{moves_hex},{', '.join(values)});\n"
                    output.write(sql)
                    counter += 1
                    print(f"\rProcessed {counter} games", end="")

                except Exception as e:
                    error_log.write(f"Error processing game: {game.headers.get('Event', '?')}\n{e}\n")

    print(f"\nProcessed {counter} games. Errors logged to errors.log.")


if __name__ == "__main__":
    main()
