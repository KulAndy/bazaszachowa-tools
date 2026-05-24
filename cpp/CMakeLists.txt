cmake_minimum_required(VERSION 3.10)

project(chess_db LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED YES)
set(SOURCE_DIR src)
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION TRUE)

if(MSVC)
    add_compile_options(/W3)
else()
    add_compile_options(-Wall)
endif()
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION TRUE)

include_directories(${SOURCE_DIR}/chess-library/include)
include_directories("/usr/include")
include_directories("/usr/include/mysql")
include_directories("/usr/include/cppconn")
link_directories("/usr/lib/x86_64-linux-gnu")

add_executable(pgn2sql ${SOURCE_DIR}/pgn2sql.cpp)
add_executable(lichess_classify ${SOURCE_DIR}/lichess_classify.cpp)
add_executable(remote2pgn ${SOURCE_DIR}/remote2pgn.cpp)

target_include_directories(lichess_classify PRIVATE
    /usr/include/mysql
    /usr/include/cppconn
    ${SOURCE_DIR}/chess-library/include
)

target_link_libraries(lichess_classify PRIVATE
    mysqlcppconn
    pthread
)

target_include_directories(remote2pgn PRIVATE
    /usr/include/mysql
    /usr/include/cppconn
    ${SOURCE_DIR}/chess-library/include
)

target_link_libraries(remote2pgn PRIVATE
    mysqlcppconn
    pthread
)
