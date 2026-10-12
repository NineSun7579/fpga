#pragma once
// Syntax-check declarations only. Never add test_support to a board build.
// There are no definitions: this cannot link or stand in for OpenCV at runtime.
#include <cstddef>
#include <string>
#define CV_8UC3 16
namespace cv {
inline constexpr int IMREAD_COLOR = 1, INTER_LINEAR = 1, COLOR_BGR2RGB = 4;
struct Size { Size(int, int); };
struct Scalar { Scalar(double, double, double); };
struct Rect { Rect(int, int, int, int); };
class Mat {
public:
    unsigned char* data = nullptr;
    int cols = 0, rows = 0;
    Mat();
    Mat(int, int, int, const Scalar&);
    bool empty() const;
    bool isContinuous() const;
    int type() const;
    Mat clone() const;
    Mat operator()(const Rect&) const;
    void copyTo(const Mat&) const;
};
class VideoCapture {
public:
    explicit VideoCapture(const std::string&);
    bool isOpened() const;
    bool read(Mat&);
};
Mat imread(const std::string&, int);
void resize(const Mat&, Mat&, const Size&, double, double, int);
void cvtColor(const Mat&, Mat&, int);
void setNumThreads(int);
} // namespace cv
