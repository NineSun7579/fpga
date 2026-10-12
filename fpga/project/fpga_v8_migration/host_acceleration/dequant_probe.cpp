// Read both packed formats from the SAME completed run. No FPS measurement.
#define main retained_pipeline_main
#include "pipeline_bench.cpp"
#undef main
#include <map>

namespace {
std::uint32_t float_bits(float f) {
    std::uint32_t bits;
    std::memcpy(&bits, &f, sizeof(bits));
    return bits;
}
float bits_float(std::uint32_t bits) {
    float f;
    std::memcpy(&f, &bits, sizeof(f));
    return f;
}
}

int main(int argc, char** argv) {
    try {
        require(argc == 5, "usage: dequant_probe MODEL FRAME_LIST PREFIX MODEL_SHA");
        cv::setNumThreads(1);
        Model model(argv[1], argv[4]);
        auto inputs = load_inputs(argv[2]);
        Session session(model);
        std::array<std::array<std::map<std::uint32_t, std::size_t>, 256>, 6> pairs;
        std::size_t raw_changed = 0, elements = 0;
        for (const auto& input : inputs) {
            auto rgb = prepare(input.bgr);
            session.set(rgb); session.run(); session.get(Profile::Native);
            std::array<std::vector<std::uint8_t>, 6> raw;
            for (int h = 0; h < 6; ++h) {
                const auto* p = static_cast<const std::uint8_t*>(session.outs[h].buf);
                raw[h].assign(p, p + session.attrs[h].n_elems);
            }
            session.release();
            session.get(Profile::Baseline);
            for (int h = 0; h < 6; ++h) {
                const auto* f = static_cast<const float*>(session.outs[h].buf);
                for (std::size_t i = 0; i < raw[h].size(); ++i) {
                    require(std::isfinite(f[i]), "non-finite runtime float");
                    ++pairs[h][raw[h][i]][float_bits(f[i])];
                    ++elements;
                }
            }
            session.release();
            session.get(Profile::Native);
            for (int h = 0; h < 6; ++h) {
                const auto* p = static_cast<const std::uint8_t*>(session.outs[h].buf);
                for (std::size_t i = 0; i < raw[h].size(); ++i) raw_changed += p[i] != raw[h][i];
            }
            session.release();
        }
        auto csv = output_file(std::string(argv[3]) + "_mapping.csv");
        csv << "head,index,type,zp,scale,byte,code,runtime_float,runtime_bits,count,affine_float,affine_bits\n";
        std::size_t ambiguous_codes = 0, observed_codes = 0;
        for (int h = 0; h < 6; ++h) {
            const auto& a = session.attrs[h];
            for (int byte = 0; byte < 256; ++byte) {
                const auto& values = pairs[h][byte];
                observed_codes += !values.empty();
                ambiguous_codes += values.size() > 1;
                const int q = raw_dfl::detail::code(std::uint8_t(byte), a.type);
                const float affine = float(q - a.zp) * a.scale;
                for (const auto& entry : values)
                    csv << a.name << ',' << a.index << ',' << int(a.type) << ',' << a.zp << ','
                        << std::setprecision(17) << a.scale << ',' << byte << ',' << q << ','
                        << bits_float(entry.first) << ',' << entry.first << ',' << entry.second << ','
                        << affine << ',' << float_bits(affine) << '\n';
            }
        }
        csv.flush();
        auto source = output_file(std::string(argv[3]) + "_metadata.json");
        const auto json = QJsonDocument(QJsonObject{{"model_sha256", qs(model.actual_sha)},
            {"same_completed_run", true}, {"acquisition_order", "raw_get/release,float_get/release,raw_get/release"},
            {"frames", int(inputs.size())}, {"elements", double(elements)}, {"raw_changed_after_float_get", double(raw_changed)},
            {"observed_head_code_pairs", double(observed_codes)}, {"codes_with_multiple_float_values", double(ambiguous_codes)},
            {"session", session.metadata(Profile::Native)}, {"runtime_library", runtime_library()}}).toJson(QJsonDocument::Indented);
        source.write(json.constData(), json.size()); source.flush();
        session.close();
        require(raw_changed == 0, "packed raw changed after float retrieval");
        std::cout << "DEQUANT_PROBE_PASS elements=" << elements << " observed_codes=" << observed_codes
                  << " ambiguous_codes=" << ambiguous_codes << '\n';
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "DEQUANT_PROBE_FAIL " << e.what() << '\n'; return 1;
    }
}
