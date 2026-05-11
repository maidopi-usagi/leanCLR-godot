cmake_minimum_required(VERSION 3.19)
project(leanclr_godot LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(LEANCLR_GODOT_FETCH_GODOT_CPP "Fetch godot-cpp when GODOT_CPP_ROOT is not provided" ON)
set(GODOT_CPP_ROOT "" CACHE PATH "Path to a checked-out godot-cpp tree")
set(GODOT_CPP_LIBRARY "" CACHE FILEPATH "Path to a prebuilt godot-cpp static library. When set, godot-cpp is imported instead of built.")
set(GODOT_CPP_GEN_INCLUDE_DIR "" CACHE PATH "Path to godot-cpp generated headers, for example <godot-cpp-build>/gen/include")
set(GODOT_CPP_BRANCH "4.4" CACHE STRING "godot-cpp branch or tag to use when fetching")

if(MSVC)
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreadedDLL" CACHE STRING "Select the MSVC runtime library for GDExtension binaries." FORCE)
endif()

function(configure_size_optimized_native_target target_name)
    if(NOT TARGET ${target_name})
        return()
    endif()

    set_target_properties(${target_name} PROPERTIES
        CXX_VISIBILITY_PRESET hidden
        VISIBILITY_INLINES_HIDDEN YES
    )

    if(NOT MSVC)
        target_compile_options(${target_name} PRIVATE -ffunction-sections -fdata-sections)
    endif()
endfunction()

set(LEANCLR_ROOT "${CMAKE_CURRENT_LIST_DIR}/thirdparty/leanclr" CACHE PATH "Path to the LeanCLR source tree")
add_subdirectory(${LEANCLR_ROOT}/src/runtime leanclr_runtime)
configure_size_optimized_native_target(leanclr)

if(MSVC)
    set_target_properties(leanclr PROPERTIES MSVC_RUNTIME_LIBRARY "MultiThreadedDLL")
endif()

if(GODOT_CPP_LIBRARY)
    if(NOT GODOT_CPP_ROOT)
        message(FATAL_ERROR "GODOT_CPP_ROOT is required when GODOT_CPP_LIBRARY is set")
    endif()
    if(NOT GODOT_CPP_GEN_INCLUDE_DIR)
        message(FATAL_ERROR "GODOT_CPP_GEN_INCLUDE_DIR is required when GODOT_CPP_LIBRARY is set")
    endif()

    add_library(godot-cpp STATIC IMPORTED GLOBAL)
    set_target_properties(godot-cpp PROPERTIES
        IMPORTED_LOCATION "${GODOT_CPP_LIBRARY}"
        INTERFACE_INCLUDE_DIRECTORIES "${GODOT_CPP_GEN_INCLUDE_DIR};${GODOT_CPP_ROOT}/include"
        INTERFACE_COMPILE_FEATURES cxx_std_17
        INTERFACE_COMPILE_DEFINITIONS "GDEXTENSION;$<$<CONFIG:Debug>:DEBUG_ENABLED>;THREADS_ENABLED;WINDOWS_ENABLED;TYPED_METHOD_BIND;NOMINMAX"
    )

    if(MSVC)
        target_compile_definitions(godot-cpp INTERFACE _HAS_EXCEPTIONS=0)
        target_compile_options(godot-cpp INTERFACE /utf-8)
        target_link_options(godot-cpp INTERFACE $<$<CONFIG:Debug>:/DEBUG:FULL>)
    endif()
elseif(GODOT_CPP_ROOT)
    add_subdirectory(${GODOT_CPP_ROOT} godot_cpp)
else()
    if(NOT LEANCLR_GODOT_FETCH_GODOT_CPP)
        message(FATAL_ERROR "Set GODOT_CPP_ROOT or enable LEANCLR_GODOT_FETCH_GODOT_CPP")
    endif()

    include(FetchContent)
    FetchContent_Declare(
        godot-cpp
        GIT_REPOSITORY https://github.com/godotengine/godot-cpp.git
        GIT_TAG ${GODOT_CPP_BRANCH}
    )
    FetchContent_MakeAvailable(godot-cpp)
endif()
configure_size_optimized_native_target(godot-cpp)

add_library(leanclr_godot SHARED
    src/generated/godot_api.generated.cpp
    src/leanclr_main_node.cpp
    src/leanclr_hot_reload_host.cpp
    src/leanclr_runtime_bridge.cpp
    src/leanclr_script.cpp
    src/leanclr_script_language.cpp
    src/leanclr_script_loader.cpp
    src/leanclr_script_saver.cpp
    src/leanclr_wasm_libcxx_shim.cpp
    src/register_types.cpp
)

target_include_directories(leanclr_godot PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/src
)

target_link_libraries(leanclr_godot PRIVATE
    godot-cpp
    leanclr
)

if(MSVC)
    target_compile_options(leanclr_godot PRIVATE /W4 /MP /bigobj)
    set_target_properties(leanclr_godot PROPERTIES MSVC_RUNTIME_LIBRARY "MultiThreadedDLL")
else()
    target_compile_options(leanclr_godot PRIVATE -Wall -Wextra -Wpedantic)
    target_compile_options(leanclr_godot PRIVATE -ffunction-sections -fdata-sections)
    if(APPLE)
        set(LEANCLR_GODOT_EXPORTED_SYMBOLS "${CMAKE_CURRENT_BINARY_DIR}/leanclr_godot.exports")
        file(WRITE "${LEANCLR_GODOT_EXPORTED_SYMBOLS}" "_leanclr_godot_library_init\n")
        target_link_options(leanclr_godot PRIVATE
            -Wl,-dead_strip
            -Wl,-exported_symbols_list,${LEANCLR_GODOT_EXPORTED_SYMBOLS}
        )
    elseif(UNIX AND NOT EMSCRIPTEN)
        target_link_options(leanclr_godot PRIVATE -Wl,--gc-sections)
    endif()
endif()

if(EMSCRIPTEN)
    target_link_options(leanclr_godot PRIVATE -sSIDE_MODULE=1)
    set_target_properties(leanclr_godot PROPERTIES SUFFIX ".wasm")
endif()

set_target_properties(leanclr_godot PROPERTIES
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN YES
)

set_target_properties(leanclr_godot PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}/project/bin/$<CONFIG>"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}/project/bin/$<CONFIG>"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}/project/bin/$<CONFIG>"
    RUNTIME_OUTPUT_DIRECTORY_DEBUG "${CMAKE_CURRENT_LIST_DIR}/project/bin/Debug"
    LIBRARY_OUTPUT_DIRECTORY_DEBUG "${CMAKE_CURRENT_LIST_DIR}/project/bin/Debug"
    ARCHIVE_OUTPUT_DIRECTORY_DEBUG "${CMAKE_CURRENT_LIST_DIR}/project/bin/Debug"
    RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_CURRENT_LIST_DIR}/project/bin/Release"
    LIBRARY_OUTPUT_DIRECTORY_RELEASE "${CMAKE_CURRENT_LIST_DIR}/project/bin/Release"
    ARCHIVE_OUTPUT_DIRECTORY_RELEASE "${CMAKE_CURRENT_LIST_DIR}/project/bin/Release"
)
