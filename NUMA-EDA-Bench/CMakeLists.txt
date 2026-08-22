cmake_minimum_required(VERSION 3.16)
project(NUMA_EDA_Bench LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(numa_mem_bench src/numa_mem_bench.cpp)
target_compile_options(numa_mem_bench PRIVATE -O3 -Wall -Wextra)

install(TARGETS numa_mem_bench RUNTIME DESTINATION bin)
