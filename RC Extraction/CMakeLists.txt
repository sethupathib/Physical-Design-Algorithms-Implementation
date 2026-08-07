cmake_minimum_required(VERSION 3.14)
project(rc_extraction LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(rcx
  src/techfile.cpp
  src/layout.cpp
  src/connectivity.cpp
  src/resistance.cpp
  src/capacitance.cpp
  src/rc_network.cpp
  src/spef_writer.cpp
  src/elmore.cpp
  src/extract.cpp
)
target_include_directories(rcx PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_options(rcx PRIVATE -Wall -Wextra -pedantic)

add_executable(rcx_extract src/main.cpp)
target_link_libraries(rcx_extract PRIVATE rcx)

add_executable(test_rc tests/test_rc.cpp)
target_link_libraries(test_rc PRIVATE rcx)

enable_testing()
add_test(NAME rc_unit COMMAND test_rc WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
