cmake_minimum_required(VERSION 3.15)

project(chess_db LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(SOURCE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/src)
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION TRUE)

if(MSVC)
    add_compile_options(/W3)
else()
    add_compile_options(-Wall -Wextra -pthread)
endif()

if(CMAKE_SYSTEM_NAME STREQUAL "FreeBSD")
    message(STATUS "Configuring for FreeBSD")

    set(MYSQL_INCLUDE_DIRS
        /usr/local/include
        /usr/local/include/mysql
    )

    set(MYSQL_LIBRARY_DIRS
        /usr/local/lib/mysql
        /usr/local/lib
    )

    set(MYSQL_PREFIX
        /usr/local
    )

elseif(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    message(STATUS "Configuring for Linux")

    if(EXISTS "/etc/alpine-release")
        message(STATUS "Configuring for Alpine")

        set(MYSQL_INCLUDE_DIRS
            /usr/include
            /usr/include/mysql
        )

        set(MYSQL_LIBRARY_DIRS
            /usr/lib
        )

        set(MYSQL_PREFIX
            /usr
        )

    else()
        set(MYSQL_INCLUDE_DIRS
            /usr/include
            /usr/include/mysql
        )

        set(MYSQL_LIBRARY_DIRS
            /usr/lib
            /usr/lib64
            /usr/lib/x86_64-linux-gnu
            /usr/lib/aarch64-linux-gnu
        )

        set(MYSQL_PREFIX
            /usr
        )

    endif()
else()
    message(FATAL_ERROR "Unsupported OS")
endif()

find_path(
    MYSQL_INCLUDE_DIR
    NAMES mysql.h
    PATHS ${MYSQL_INCLUDE_DIRS}
)

find_library(
    MYSQL_CLIENT_LIBRARY
    NAMES mysqlclient mariadb
    PATHS ${MYSQL_LIBRARY_DIRS}
)


if(NOT MYSQL_INCLUDE_DIR)
    message(FATAL_ERROR
        "Could not find MySQL C client headers (mysql.h). "
        "Install the MySQL/MariaDB development package."
    )
endif()


if(NOT MYSQL_CLIENT_LIBRARY)
    message(FATAL_ERROR
        "Could not find MySQL C client library "
        "(libmysqlclient or libmariadb). "
        "Install the MySQL/MariaDB development package."
    )

endif()


message(STATUS "MySQL C headers: ${MYSQL_INCLUDE_DIR}")
message(STATUS "MySQL C library: ${MYSQL_CLIENT_LIBRARY}")

set(MYSQL_CPP_SOURCE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/mysql-connector-cpp)
set(MYSQL_CPP_BUILD_DIR ${MYSQL_CPP_SOURCE_DIR}/build)

if(NOT EXISTS ${MYSQL_CPP_SOURCE_DIR}/CMakeLists.txt)
    message(FATAL_ERROR
        "MySQL Connector/C++ submodule was not found:\n"
        "  ${MYSQL_CPP_SOURCE_DIR}\n"
        "Initialize the git submodule first."
    )
endif()


add_custom_target(
    mysql_connector_cpp
    ALL

    COMMAND
        ${CMAKE_COMMAND}
        -S ${MYSQL_CPP_SOURCE_DIR}
        -B ${MYSQL_CPP_BUILD_DIR}

        -DWITH_JDBC=ON
        -DWITH_XPROTOCOL=OFF

        -DWITH_MYSQL=${MYSQL_PREFIX}
        -DMYSQL_INCLUDE_DIR=${MYSQL_INCLUDE_DIR}
        -DMYSQL_LIB_DIR=${MYSQL_LIBRARY_DIRS}

        -DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}

    COMMAND
        ${CMAKE_COMMAND}
        --build ${MYSQL_CPP_BUILD_DIR}
        --parallel

    WORKING_DIRECTORY
        ${MYSQL_CPP_SOURCE_DIR}

    COMMENT
        "Building MySQL Connector/C++ JDBC"
)


set(MYSQL_CPP_INCLUDE_DIR ${MYSQL_CPP_SOURCE_DIR}/include)
set(MYSQL_CPP_JDBC_INCLUDE_DIR ${MYSQL_CPP_BUILD_DIR}/include/jdbc)
set(MYSQL_CPP_CPPCONN_INCLUDE_DIR ${MYSQL_CPP_BUILD_DIR}/include/jdbc/cppconn)


if(WIN32)
    set(MYSQL_CPP_JDBC_LIBRARY ${MYSQL_CPP_BUILD_DIR}/jdbc/mysqlcppconn.lib)
elseif(APPLE)
    set(MYSQL_CPP_JDBC_LIBRARY ${MYSQL_CPP_BUILD_DIR}/jdbc/libmysqlcppconn.dylib)
else()
    set(MYSQL_CPP_JDBC_LIBRARY ${MYSQL_CPP_BUILD_DIR}/jdbc/libmysqlcppconn.so)

endif()


include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${MYSQL_CPP_INCLUDE_DIR}
    ${MYSQL_CPP_JDBC_INCLUDE_DIR}
    ${MYSQL_CPP_CPPCONN_INCLUDE_DIR}
    ${MYSQL_INCLUDE_DIR}
)

link_directories(
    ${MYSQL_CPP_BUILD_DIR}/jdbc
    ${MYSQL_LIBRARY_DIRS}
)

add_executable(pgn2sql ${SOURCE_DIR}/pgn2sql.cpp)
add_executable(lichess_classify ${SOURCE_DIR}/lichess_classify.cpp)
add_executable(remote2pgn ${SOURCE_DIR}/remote2pgn.cpp)
add_executable(prepare_pgn ${SOURCE_DIR}/prepare_pgn.cpp)

target_link_libraries(lichess_classify PRIVATE
        ${MYSQL_CPP_JDBC_LIBRARY}
        ${MYSQL_CLIENT_LIBRARY}
        pthread
)

add_dependencies(lichess_classify mysql_connector_cpp)
if(APPLE)
    set_target_properties(
        lichess_classify
        PROPERTIES

            BUILD_RPATH
            "${MYSQL_CPP_BUILD_DIR}/jdbc"

            INSTALL_RPATH
            "@loader_path"
    )

elseif(UNIX)
    set_target_properties(
        lichess_classify
        PROPERTIES

            BUILD_RPATH
            "${MYSQL_CPP_BUILD_DIR}/jdbc"

            INSTALL_RPATH
            "${MYSQL_CPP_BUILD_DIR}/jdbc"
    )

endif()


target_link_libraries(remote2pgn PRIVATE
        ${MYSQL_CLIENT_LIBRARY}
        pthread
)

target_link_libraries(pgn2sql PRIVATE
        ${MYSQL_CLIENT_LIBRARY}
        pthread
)
