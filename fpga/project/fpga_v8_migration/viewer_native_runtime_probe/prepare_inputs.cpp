#include <QCryptographicHash>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#include <cmath>
#include <iostream>
#include <stdexcept>

// Exact prepare() bytes imported from retained host_acceleration/pipeline_bench.cpp.
#include "pipeline_prepare.inc"

QByteArray read(const QString& path) {
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) throw std::runtime_error("cannot read " + path.toStdString());
    return file.readAll();
}
QString hash(const QByteArray& data) { return QCryptographicHash::hash(data, QCryptographicHash::Sha256).toHex(); }
int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::runtime_error("usage: prepare_inputs STAGE");
        const auto stage = QString::fromLocal8Bit(argv[1]);
        cv::setNumThreads(1);
        const auto expectations = QJsonDocument::fromJson(read(stage + "/input_expectations.json")).object();
        QJsonArray rows;
        for (const auto& value : expectations.value("inputs").toArray()) {
            auto row = value.toObject();
            const auto png = row.value("board_path").toString();
            if (hash(read(png)) != row.value("png_sha256").toString()) throw std::runtime_error("PNG hash mismatch");
            const auto bgr = cv::imread(png.toStdString(), cv::IMREAD_COLOR);
            if (bgr.empty() || bgr.type() != CV_8UC3) throw std::runtime_error("invalid retained image");
            const auto rgb = prepare(bgr);
            if (!rgb.isContinuous()) throw std::runtime_error("RGB is not contiguous");
            const auto data = QByteArray::fromRawData(reinterpret_cast<const char*>(rgb.data), 1228800);
            if (hash(data) != row.value("rgb_sha256").toString()) throw std::runtime_error("retained pipeline RGB hash mismatch");
            const auto path = stage + QString("/frame_%1.rgb").arg(rows.size()+1, 2, 10, QLatin1Char('0'));
            QFile output(path);
            if (!output.open(QIODevice::WriteOnly) || output.write(data) != data.size()) throw std::runtime_error("cannot write prepared RGB");
            row.insert("prepared_path", path); row.insert("actual_rgb_sha256", hash(data)); row.insert("bytes", data.size());
            rows.append(row);
        }
        if (rows.size() != 30) throw std::runtime_error("requires exactly 30 retained frames");
        QFile output(stage + "/prepared_inputs.json");
        if (!output.open(QIODevice::WriteOnly)) throw std::runtime_error("cannot save manifest");
        output.write(QJsonDocument(QJsonObject{{"inputs", rows}, {"opencv_version", CV_VERSION},
            {"preparation", "byte-exact retained pipeline prepare(); all RGB bytes verified by historical SHA256"}}).toJson(QJsonDocument::Indented));
        std::cout << "PREPARED_INPUTS_HASH_PASS 30\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
