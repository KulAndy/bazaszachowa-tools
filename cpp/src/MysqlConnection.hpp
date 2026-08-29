#pragma once

#include <mysql/mysql.h>

#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>

namespace mysql {

struct ConnectionDeleter {
  void operator()(MYSQL *conn) const noexcept {
    if (conn) {
      mysql_close(conn);
    }
  }
};

struct ResultDeleter {
  void operator()(MYSQL_RES *result) const noexcept {
    if (result) {
      mysql_free_result(result);
    }
  }
};

using ConnectionPtr = std::unique_ptr<MYSQL, ConnectionDeleter>;
using ResultPtr = std::unique_ptr<MYSQL_RES, ResultDeleter>;

class Result {
public:
  explicit Result(MYSQL_RES *result) noexcept : result_(result) {}

  Result(const Result &) = delete;
  Result &operator=(const Result &) = delete;

  Result(Result &&) noexcept = default;
  Result &operator=(Result &&) noexcept = default;

  ~Result() = default;

  MYSQL_ROW fetchRow() noexcept { return mysql_fetch_row(result_.get()); }

  unsigned long *fetchLengths() noexcept {
    return mysql_fetch_lengths(result_.get());
  }

  explicit operator bool() const noexcept { return static_cast<bool>(result_); }

private:
  ResultPtr result_;
};

class Connection {
public:
  Connection(const char *host, const char *user, const char *password,
             const char *database, unsigned int port = 0) {

    ConnectionPtr connection(mysql_init(nullptr));

    if (!connection) {
      throw std::runtime_error("mysql_init() failed");
    }

    if (!mysql_real_connect(connection.get(), host, user, password, database,
                            port, nullptr, 0)) {

      throw std::runtime_error("MySQL connection failed: " +
                               std::string(mysql_error(connection.get())));
    }

    connection_ = std::move(connection);
  }

  Connection(const Connection &) = delete;
  Connection &operator=(const Connection &) = delete;

  Connection(Connection &&) noexcept = default;
  Connection &operator=(Connection &&) noexcept = default;

  ~Connection() = default;

  void query(std::string_view sql) {
    std::string query_string(sql);

    if (mysql_query(connection_.get(), query_string.c_str())) {
      throwError("MySQL query failed");
    }
  }

  Result storeResult() {
    MYSQL_RES *result = mysql_store_result(connection_.get());

    if (!result) {
      throwError("mysql_store_result() failed");
    }

    return Result(result);
  }

  Result queryResult(std::string_view sql) {
    query(sql);
    return storeResult();
  }

  const char *error() const noexcept { return mysql_error(connection_.get()); }

  unsigned int errorNumber() const noexcept {
    return mysql_errno(connection_.get());
  }

  bool hasError() const noexcept { return mysql_errno(connection_.get()) != 0; }

private:
  ConnectionPtr connection_;

  [[noreturn]]
  void throwError(std::string_view prefix) const {
    throw std::runtime_error(std::string(prefix) + ": " +
                             mysql_error(connection_.get()));
  }
};

} // namespace mysql
