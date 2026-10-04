cmake_minimum_required(VERSION 3.16)
project(detview_stereo_demo LANGUAGES CXX)

find_package(OpenCV 4 REQUIRED COMPONENTS core imgproc imgcodecs calib3d highgui)
find_package(Threads REQUIRED)
add_executable(detview_stereo_demo
    main.cpp stereo_depth.cpp stereo_selftest.cpp pango_stereo_source.cpp)
target_compile_features(detview_stereo_demo PRIVATE cxx_std_17)
target_compile_options(detview_stereo_demo PRIVATE -Wall -Wextra -Wpedantic)
target_include_directories(detview_stereo_demo PRIVATE ${OpenCV_INCLUDE_DIRS})
target_link_libraries(detview_stereo_demo PRIVATE ${OpenCV_LIBS} Threads::Threads)

include(CTest)
if(BUILD_TESTING)
    add_test(NAME stereo_geometry_and_matching COMMAND detview_stereo_demo --self-test)
    add_test(NAME stereo_synthetic_headless COMMAND detview_stereo_demo
        --synthetic --headless --output ${CMAKE_CURRENT_BINARY_DIR}/synthetic_output)
    set_tests_properties(stereo_synthetic_headless PROPERTIES FIXTURES_SETUP saved_pair)
    add_test(NAME stereo_uncalibrated_headless COMMAND detview_stereo_demo
        --left-image ${CMAKE_CURRENT_BINARY_DIR}/synthetic_output/left_raw.png
        --right-image ${CMAKE_CURRENT_BINARY_DIR}/synthetic_output/right_raw.png
        --headless --output ${CMAKE_CURRENT_BINARY_DIR}/uncalibrated_output)
    set_tests_properties(stereo_uncalibrated_headless PROPERTIES FIXTURES_REQUIRED saved_pair)
    add_test(NAME stereo_reject_empty_calibration COMMAND detview_stereo_demo
        --left-image ${CMAKE_CURRENT_BINARY_DIR}/synthetic_output/left_raw.png
        --right-image ${CMAKE_CURRENT_BINARY_DIR}/synthetic_output/right_raw.png
        --calibration ${CMAKE_CURRENT_SOURCE_DIR}/calibration.template.yml
        --headless --output ${CMAKE_CURRENT_BINARY_DIR}/invalid_output)
    set_tests_properties(stereo_reject_empty_calibration PROPERTIES
        FIXTURES_REQUIRED saved_pair WILL_FAIL TRUE)
endif()
