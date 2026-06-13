import re
import sys
import threading
import traceback
from mysql.connector import pooling
from settings import SETTINGS

POOL_SIZE = 8
db_pool = None
unique_years = set()


def init_db_pool():
    global db_pool
    db_pool = pooling.MySQLConnectionPool(
        pool_name="my_pool",
        pool_size=POOL_SIZE,
        pool_reset_session=True,
        **SETTINGS["mysql"]
    )


def fetch_duplicate_games(table):
    global db_pool
    connection = db_pool.get_connection()
    cursor = connection.cursor(buffered=True)
    try:
        sql = f"""
            SELECT JSON_ARRAYAGG(id)
            FROM `{table}_games`
            GROUP BY 
            WhiteID, BlackID, ecoID, 
            WhiteElo, 
            BlackElo, 
            LEFT(moves_blob, 15 * 2 *2), result
            HAVING COUNT(*) > 1;
        """
        cursor.execute(sql)
        while True:
            batch = cursor.fetchmany(1_000)
            if not batch:
                break
            yield batch
    finally:
        cursor.close()
        connection.close()


def fetch_game_details(table, ids):
    global db_pool
    connection = None
    cursor = None
    try:
        connection = db_pool.get_connection()
        cursor = connection.cursor(buffered=True)
        ids = re.sub(r"\[|\]", "", ",".join(ids))
        sql = f"""
            SELECT id, moves_blob, Year, Month, Day
            FROM {table}_games
            WHERE id IN ({ids})
            ORDER BY moves_blob
        """
        cursor.execute(sql)
        return cursor.fetchall()
    except Exception as e:
        print(f"Error fetching game details: {str(e)}")
        traceback.print_exc()
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def process_duplicates(table, lock, duplicates):
    try:
        for rows in fetch_duplicate_games(table):
            local_duplicates = 0
            if rows:
                game_ids = [row[0] for row in rows]
                games = fetch_game_details(table, game_ids)
                if not games:
                    continue

                connection = None
                cursor = None
                try:
                    connection = db_pool.get_connection()
                    connection.autocommit = True
                    cursor = connection.cursor()

                    delete_game_sql = f"DELETE FROM {table}_games WHERE id = %s"
                    update_game_sql = (f"UPDATE {table}_games SET "
                                       "Year = %s, "
                                       "Month = %s, "
                                       "Day = %s "
                                       "WHERE id = %s")

                    delete_params = []
                    update_params = []

                    for i in range(1, len(games)):
                        game_id1, moves1, year1, month1, day1 = games[i - 1]
                        game_id2, moves2, year2, month2, day2 = games[i]

                        month1 = month1 or 0
                        day1 = day1 or 0
                        month2 = month2 or 0
                        day2 = day2 or 0

                        if moves2 == moves1:
                            if (year1, month1, day1) < (year2, month2, day2):
                                print(f"{game_id1} > {game_id2}")
                                delete_params.append((game_id2,))
                            else:
                                print(f"{game_id2} > {game_id1}")
                                delete_params.append((game_id1,))
                            local_duplicates += 1

                        elif moves2.startswith(moves1):
                            print(f"{game_id1} > {game_id2}")
                            delete_params.append((game_id2,))
                            if (year2, month2, day2) < (year1, month1, day1):
                                update_params.append((year2, month2, day2, game_id1))
                            local_duplicates += 1

                        elif moves1.startswith(moves2):
                            print(f"{game_id2} > {game_id1}")
                            delete_params.append((game_id1,))
                            if (year1, month1, day1) < (year2, month2, day2):
                                update_params.append((year1, month1, day1, game_id2))
                            local_duplicates += 1


                        if len(update_params) >= 1000:
                            cursor.executemany(update_game_sql, update_params)
                            connection.commit()
                            update_params = []

                        if len(delete_params) >= 1000:
                            cursor.executemany(delete_game_sql, delete_params)
                            connection.commit()
                            delete_params = []

                    if update_params:
                        cursor.executemany(update_game_sql, update_params)
                        connection.commit()

                    if delete_params:
                        cursor.executemany(delete_game_sql, delete_params)
                        connection.commit()

                except Exception as e:
                    print(f"Error processing batch: {str(e)}")
                    traceback.print_exc()
                    if connection:
                        connection.rollback()
                finally:
                    if cursor:
                        cursor.close()
                    if connection:
                        connection.close()

                if local_duplicates > 0:
                    print(f"Duplicates processed: {local_duplicates}")

                with lock:
                    duplicates[0] += local_duplicates
    except Exception as e:
        print(f"Error in process_duplicates: {str(e)}")
        traceback.print_exc()


def main():
    global db_pool
    init_db_pool()
    try:
        TABLE = sys.argv[1] if len(sys.argv) > 1 else "all"
    except Exception as e:
        print(f"Error parsing table name: {str(e)}")
        TABLE = "all"

    try:
        duplicates = [0]
        lock = threading.Lock()
        process_duplicates(TABLE, lock, duplicates)
        return duplicates[0]
    except Exception as e:
        print(f"Error in main process: {str(e)}")
        traceback.print_exc()
        return 0


if __name__ == "__main__":
    duplicates = main()
    print(f"Total duplicates processed: {duplicates}")
