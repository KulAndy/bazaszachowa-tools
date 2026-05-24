import re
import sys
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def fetch_duplicate_games(year, table):
    connection = db_pool.get_connection()
    cursor = connection.cursor(buffered=True)
    try:
        sql = f"""
        SELECT JSON_ARRAYAGG({table}_games.id)
        FROM `{table}_games`
        INNER JOIN {table}_players AS a1 ON {table}_games.WhiteID = a1.id
        INNER JOIN {table}_players AS a2 ON {table}_games.BlackID = a2.id
        WHERE Year = %s
        GROUP BY SUBSTRING_INDEX(a1.fullname, ",", 1), SUBSTRING_INDEX(a2.fullname, ",", 1), Year, LEFT(moves_blob, 3 * 2)
        HAVING COUNT(*) > 1;
        """
        cursor.execute(sql, (year,))
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def fetch_game_details(table, ids):
    global db_pool
    connection = db_pool.get_connection()
    cursor = connection.cursor(buffered=True)
    try:
        ids = re.sub(r"\[|\]", "", ",".join(ids))
        sql = fr"""
        SELECT {table}_games.id, moves_blob,
        a1.id as whiteID, REGEXP_REPLACE(a1.fullname, "[\\s,.]+", " ") as white,
        a2.id as blackID, REGEXP_REPLACE(a2.fullname, "[\\s,.]+", " ") as black
        FROM {table}_games
        INNER JOIN {table}_players AS a1 ON {table}_games.WhiteID = a1.id
        INNER JOIN {table}_players AS a2 ON {table}_games.BlackID = a2.id
        WHERE {table}_games.id IN ({ids})
        ORDER BY moves_blob
"""
        cursor.execute(sql)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def process_year(year, table, lock, duplicates):
    print(year)
    if year in unique_years:
        return
    try:
        rows = fetch_duplicate_games(year, table)
        local_duplicates = 0
        if rows:
            game_ids = [id for row in rows for id in row]
            games = fetch_game_details(table, game_ids)
            connection = db_pool.get_connection()
            connection.autocommit = True
            cursor = connection.cursor()
            try:
                update_white_sql = f"UPDATE {table}_games SET whiteID = %s WHERE id = %s"
                update_black_sql = f"UPDATE {table}_games SET blackID = %s WHERE id = %s"
                update_event_sql = f"""
                UPDATE {table}_games as t1
                JOIN {table}_games as t2
                INNER JOIN chess_events ON chess_events.id = t1.id
                SET t1.eventID = t2.eventID
                WHERE t1.id = %s AND t2.id = %s AND chess_events.name = '?'
                """
                update_site_sql = f"""
                UPDATE {table}_games as t1
                JOIN {table}_games as t2
                INNER JOIN sites ON sites.id = t1.id
                SET t1.siteID = t2.siteID
                WHERE t1.id = %s AND t2.id = %s AND sites.site = '?'
                """

                update_date_sql = f"""
                UPDATE {table}_games as t1
                JOIN {table}_games as t2
                SET 
                t1.Month = IFNULL(t1.Month, t2.Month),
                t1.Day = IFNULL(t1.Day, t2.Day)                
                WHERE t1.id = %s AND t2.id = %s
                """

                delete_game_sql = f"DELETE FROM {table}_games WHERE id = %s"

                params1 = []
                params2 = []
                for i in range(1, len(games)):
                    game_id1, moves1, white_id1, white1, black_id1, black1 = games[i - 1]
                    game_id2, moves2, white_id2, white2, black_id2, black2 = games[i]
                    similar = False

                    if white1.startswith(white2):
                        cursor.execute(update_white_sql, (white_id1, game_id2))
                        similar = True
                    elif white2.startswith(white1):
                        cursor.execute(update_white_sql, (white_id2, game_id1))
                        similar = True

                    if black1.startswith(black2):
                        cursor.execute(update_black_sql, (black_id1, game_id2))
                        similar = True
                    elif black2.startswith(black1):
                        cursor.execute(update_black_sql, (black_id2, game_id1))
                        similar = True

                    if similar:
                        if moves2.startswith(moves1):
                            params1.append((game_id2, game_id1))
                            params2.append((game_id1,))
                            local_duplicates += 1
                        elif moves1.startswith(moves2):
                            params1.append((game_id1, game_id2))
                            params2.append((game_id2,))
                            local_duplicates += 1

                        if len(params1) >= 1000:
                            cursor.executemany(update_event_sql, params1)
                            cursor.executemany(update_site_sql, params1)
                            cursor.executemany(update_date_sql, params1)
                            cursor.executemany(delete_game_sql, params2)
                            connection.commit()

                            params1 = []
                            params2 = []

                if params1:
                    cursor.executemany(update_event_sql, params1)
                    cursor.executemany(update_site_sql, params1)
                    cursor.executemany(update_date_sql, params1)
                    cursor.executemany(delete_game_sql, params2)

                connection.commit()
            except Exception as e:
                print(e)
            finally:
                cursor.close()
                connection.close()
            if local_duplicates > 0:
                print(f"Year {year} duplicates: {local_duplicates}")
        with lock:
            duplicates[0] += local_duplicates
            if local_duplicates == 0:
                unique_years.add(year)
    except Exception as e:
        print(traceback.format_exc())
        print(f"Error processing year {year}: {str(e)}")


def main():
    global db_pool
    init_db_pool()
    try:
        try:
            TABLE = sys.argv[1]
        except IndexError:
            TABLE = "all"
            # TABLE = "poland"

        connection = db_pool.get_connection()
        cursor = connection.cursor()
        cursor.execute(f"SELECT DISTINCT Year FROM `{TABLE}_games`")
        years = [item for sublist in cursor.fetchall() for item in sublist]
        years.sort(reverse=True)
        cursor.close()
        connection.close()
        duplicates = [0]
        lock = threading.Lock()
        with ThreadPoolExecutor(max_workers=POOL_SIZE) as executor:
            futures = [
                executor.submit(process_year, year, TABLE, lock, duplicates)
                for year in years
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(traceback.format_exc())
                    print(f"Error in processing: {str(e)}")

        if duplicates[0] > 0:
            duplicates[0] += main()

        return duplicates[0]
    except Exception as e:
        print(traceback.format_exc())
        print(f"Error in main process: {str(e)}")


if __name__ == "__main__":
    duplicates = main()
    print(f"Total duplicates processed: {duplicates}")
