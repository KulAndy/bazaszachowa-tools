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

    set(MYSQL_PREFIX /usr/local)
    set(MYSQL_INCLUDE_DIRS
        /usr/local/include/mysql
        /usr/local/include
    )
    set(MYSQL_LIBRARY_DIRS
        /usr/local/lib/mysql
        /usr/local/lib
    )

elseif(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    message(STATUS "Configuring for Linux")

    if(EXISTS "/etc/alpine-release")
        message(STATUS "Configuring for Alpine")

        set(MYSQL_PREFIX /usr)

        set(MYSQL_INCLUDE_DIRS
            /usr/include/mysql
            /usr/include
        )

        set(MYSQL_LIBRARY_DIRS
            /usr/lib
            /usr/lib64
        )

    else()
        message(STATUS "Configuring for Ubuntu/Debian")

        set(MYSQL_PREFIX /usr)

        set(MYSQL_INCLUDE_DIRS
            /usr/include/mysql
            /usr/include
        )

        set(MYSQL_LIBRARY_DIRS
            /usr/lib
            /usr/lib64
            /usr/lib/x86_64-linux-gnu
            /usr/lib/aarch64-linux-gnu
        )

    endif()
else()
    message(FATAL_ERROR "Unsupported OS: ${CMAKE_SYSTEM_NAME}")
endif()

find_path(
    MYSQL_INCLUDE_DIR
    NAMES mysql.h
    PATHS ${MYSQL_INCLUDE_DIRS}
    NO_DEFAULT_PATH
)

find_library(
    MYSQL_CLIENT_LIBRARY
    NAMES mysqlclient mariadb
    PATHS ${MYSQL_LIBRARY_DIRS}
    NO_DEFAULT_PATH
)

if(NOT MYSQL_INCLUDE_DIR)
    message(FATAL_ERROR
        "Could not find MySQL C client headers (mysql.h). "
        "Install the MySQL/MariaDB development package."
    )
endif()

if(NOT MYSQL_CLIENT_LIBRARY)
    message(FATAL_ERROR
        "Could not find MySQL C client library. "
        "Install the MySQL/MariaDB development package."
    )
endif()

get_filename_component(
    MYSQL_CLIENT_LIBRARY_DIR
    "${MYSQL_CLIENT_LIBRARY}"
    DIRECTORY
)

message(STATUS "MySQL C headers: ${MYSQL_INCLUDE_DIR}")
message(STATUS "MySQL C library: ${MYSQL_CLIENT_LIBRARY}")
message(STATUS "MySQL C library directory: ${MYSQL_CLIENT_LIBRARY_DIR}")

set(MYSQL_CPP_SOURCE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/mysql-connector-cpp)
set(MYSQL_CPP_BUILD_DIR ${MYSQL_CPP_SOURCE_DIR}/build)

find_file(
    MYSQL_CPP_SYSTEM_LIBRARY
    NAMES libmysqlcppconn.so
    PATHS
        /usr/lib/x86_64-linux-gnu
        /usr/lib/aarch64-linux-gnu
        /usr/lib
        /usr/lib64
        /usr/local/lib
        /usr/local/lib64
        /usr/local/lib/mysql
    NO_DEFAULT_PATH
)

find_file(
    MYSQL_CPP_SYSTEM_DRIVER_HEADER
    NAMES mysql_driver.h
    PATHS
        /usr/include
        /usr/local/include
    NO_DEFAULT_PATH
)

find_file(
    MYSQL_CPP_SYSTEM_CPPCONN_HEADER
    NAMES cppconn/driver.h
    PATHS
        /usr/include
        /usr/local/include
    NO_DEFAULT_PATH
)


if(
    MYSQL_CPP_SYSTEM_LIBRARY
    AND MYSQL_CPP_SYSTEM_DRIVER_HEADER
    AND MYSQL_CPP_SYSTEM_CPPCONN_HEADER
)

    get_filename_component(
        MYSQL_CPP_SYSTEM_INCLUDE_DIR
        "${MYSQL_CPP_SYSTEM_DRIVER_HEADER}"
        DIRECTORY
    )

    message(STATUS "Using system MySQL Connector/C++")
    message(STATUS "  Library: ${MYSQL_CPP_SYSTEM_LIBRARY}")
    message(STATUS "  Include: ${MYSQL_CPP_SYSTEM_INCLUDE_DIR}")

    set(MYSQL_CPP_JDBC_LIBRARY ${MYSQL_CPP_SYSTEM_LIBRARY})
    set(MYSQL_CPP_INCLUDE_DIR ${MYSQL_CPP_SYSTEM_INCLUDE_DIR})
    set(MYSQL_CPP_JDBC_INCLUDE_DIR ${MYSQL_CPP_SYSTEM_INCLUDE_DIR})
    set(MYSQL_CPP_CPPCONN_INCLUDE_DIR ${MYSQL_CPP_SYSTEM_INCLUDE_DIR})

    get_filename_component(
        MYSQL_CPP_LIBRARY_DIR
        "${MYSQL_CPP_SYSTEM_LIBRARY}"
        DIRECTORY
    )

else()

    message(STATUS "System MySQL Connector/C++ not found")
    message(STATUS "Building MySQL Connector/C++ submodule")

    if(NOT EXISTS "${MYSQL_CPP_SOURCE_DIR}/CMakeLists.txt")
        message(FATAL_ERROR
            "MySQL Connector/C++ submodule was not found:\n"
            "  ${MYSQL_CPP_SOURCE_DIR}\n"
            "Initialize the git submodule first."
        )
    endif()

    set(BUILD_JOBS "$ENV{CMAKE_BUILD_PARALLEL_LEVEL}"
        CACHE STRING "Number of parallel build jobs"
    )

    if(NOT BUILD_JOBS)
        include(ProcessorCount)
        ProcessorCount(BUILD_JOBS)

        if(NOT BUILD_JOBS OR BUILD_JOBS LESS 1)
            set(BUILD_JOBS 1)
        endif()
    endif()

message(STATUS "Build jobs: ${BUILD_JOBS}")

    if(NOT CMAKE_BUILD_TYPE)
        set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
    endif()

    if(WIN32)
        set(MYSQL_CPP_JDBC_LIBRARY
            ${MYSQL_CPP_BUILD_DIR}/jdbc/mysqlcppconn.lib
        )
    elseif(APPLE)
        set(MYSQL_CPP_JDBC_LIBRARY
            ${MYSQL_CPP_BUILD_DIR}/jdbc/libmysqlcppconn.dylib
        )
    else()
        set(MYSQL_CPP_JDBC_LIBRARY
            ${MYSQL_CPP_BUILD_DIR}/jdbc/libmysqlcppconn.so
        )
    endif()


    set(MYSQL_CPP_INCLUDE_DIR ${MYSQL_CPP_SOURCE_DIR}/include)
    set(MYSQL_CPP_JDBC_INCLUDE_DIR ${MYSQL_CPP_BUILD_DIR}/include/jdbc)
    set(MYSQL_CPP_CPPCONN_INCLUDE_DIR ${MYSQL_CPP_BUILD_DIR}/include/jdbc/cppconn)

    add_custom_target(
        mysql_connector_cpp
        ALL

        COMMAND
            ${CMAKE_COMMAND}
            -S ${MYSQL_CPP_SOURCE_DIR}
            -B ${MYSQL_CPP_BUILD_DIR}

            -DWITH_JDBC=ON
            -DWITH_XPROTOCOL=OFF
            -DWITH_SSL=system
            -DWITH_ZLIB=system
            -DWITH_PROTOBUF=system
            -DWITH_UNIT_TESTS=OFF
            -DWITH_ROUTER=OFF
            -DWITH_TESTS=OFF
            -DWITH_DOCS=OFF
            -DWITH_MAN_PAGES=OFF

            -DWITH_MYSQL=${MYSQL_PREFIX}
            -DMYSQL_INCLUDE_DIR=${MYSQL_INCLUDE_DIR}
            -DMYSQL_LIB_DIR=${MYSQL_CLIENT_LIBRARY_DIR}

            -DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}

        COMMAND
            ${CMAKE_COMMAND}
            --build ${MYSQL_CPP_BUILD_DIR}
            --parallel ${BUILD_JOBS}

        WORKING_DIRECTORY
            ${MYSQL_CPP_SOURCE_DIR}

        COMMENT
            "Building MySQL Connector/C++ JDBC"
    )


    get_filename_component(
        MYSQL_CPP_LIBRARY_DIR
        "${MYSQL_CPP_JDBC_LIBRARY}"
        DIRECTORY
    )

endif()


add_executable(pgn2sql ${SOURCE_DIR}/pgn2sql.cpp)
add_executable(lichess_classify ${SOURCE_DIR}/lichess_classify.cpp)
add_executable(remote2pgn ${SOURCE_DIR}/remote2pgn.cpp)
add_executable(prepare_pgn ${SOURCE_DIR}/prepare_pgn.cpp)

target_include_directories(
    lichess_classify
    PRIVATE

        ${MYSQL_INCLUDE_DIR}
        ${MYSQL_CPP_INCLUDE_DIR}
        ${MYSQL_CPP_JDBC_INCLUDE_DIR}
        ${MYSQL_CPP_CPPCONN_INCLUDE_DIR}
)


target_include_directories(
    remote2pgn
    PRIVATE

        ${CMAKE_CURRENT_SOURCE_DIR}
        ${MYSQL_INCLUDE_DIR}
)


target_include_directories(
    pgn2sql
    PRIVATE

        ${CMAKE_CURRENT_SOURCE_DIR}
        ${MYSQL_INCLUDE_DIR}
)

target_include_directories(
    prepare_pgn
    PRIVATE

        ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(
    lichess_classify
    PRIVATE
        ${MYSQL_CPP_JDBC_LIBRARY}
        ${MYSQL_CLIENT_LIBRARY}
        pthread
)

target_link_libraries(
    remote2pgn
    PRIVATE

        ${MYSQL_CLIENT_LIBRARY}
        pthread
)


target_link_libraries(
    pgn2sql
    PRIVATE

        ${MYSQL_CLIENT_LIBRARY}
        pthread
)


if(TARGET mysql_connector_cpp)

    add_dependencies(
        lichess_classify
        mysql_connector_cpp
    )

endif()

if(UNIX)
    set_target_properties(
        lichess_classify
        PROPERTIES

            BUILD_RPATH
                "${MYSQL_CPP_LIBRARY_DIR}"

            INSTALL_RPATH
                "${MYSQL_CPP_LIBRARY_DIR}"
    )

endif()
