#include "yolo26_rknn.h"
#include "rknn_api.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <algorithm>
#include <cmath>

Yolo26Rknn::~Yolo26Rknn() { unload(); }

bool Yolo26Rknn::load(const std::string &path, std::string &err) {
    unload();

    FILE *fp = fopen(path.c_str(), "rb");
    if (!fp) { err = "cannot open model: " + path; return false; }
    fseek(fp, 0, SEEK_END);
    long sz = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    std::vector<uint8_t> model(sz);
    if (fread(model.data(), 1, sz, fp) != (size_t)sz) { fclose(fp); err = "short read"; return false; }
    fclose(fp);

    rknn_context ctx = 0;
    int ret = rknn_init(&ctx, model.data(), (uint32_t)sz, 0, nullptr);
    if (ret < 0) { err = "rknn_init failed ret=" + std::to_string(ret); return false; }
    ctx_ = (void *)ctx;

    rknn_input_output_num io_num;
    ret = rknn_query((rknn_context)ctx_, RKNN_QUERY_IN_OUT_NUM, &io_num, sizeof(io_num));
    if (ret < 0) { err = "query IN_OUT_NUM failed"; unload(); return false; }
    if (io_num.n_input != 1 || (io_num.n_output != 1 && io_num.n_output != 2)) {
        err = "expect 1 input / 1-2 outputs, got " + std::to_string(io_num.n_input) + "/" +
              std::to_string(io_num.n_output);
        unload(); return false;
    }
    n_out_ = (int)io_num.n_output;

    rknn_tensor_attr in_attr;
    memset(&in_attr, 0, sizeof(in_attr));
    in_attr.index = 0;
    rknn_query((rknn_context)ctx_, RKNN_QUERY_INPUT_ATTR, &in_attr, sizeof(in_attr));
    mw_ = in_attr.dims[in_attr.n_dims - 2];   // NHWC: [1,640,640,3]
    mh_ = in_attr.dims[in_attr.n_dims - 3];
    if (mw_ <= 0 || mh_ <= 0 || mw_ > 4096 || mh_ > 4096) { mw_ = 640; mh_ = 640; }
    in_zp_ = in_attr.zp; in_scale_ = in_attr.scale;

    rknn_tensor_attr out_attr;
    memset(&out_attr, 0, sizeof(out_attr));
    out_attr.index = 0;
    rknn_query((rknn_context)ctx_, RKNN_QUERY_OUTPUT_ATTR, &out_attr, sizeof(out_attr));
    out_zp_ = out_attr.zp; out_scale_ = out_attr.scale;

    // [SPLIT] YOLO11 head exported as two tensors: boxes [1,4,8400] + scores
    // [1,nc,8400]. Keep the class scores in their own quantization domain.
    if (n_out_ == 2) {
        rknn_tensor_attr oa[2];
        for (int i = 0; i < 2; ++i) {
            memset(&oa[i], 0, sizeof(oa[i]));
            oa[i].index = (uint32_t)i;
            if (rknn_query((rknn_context)ctx_, RKNN_QUERY_OUTPUT_ATTR, &oa[i], sizeof(oa[i])) < 0) {
                err = "query output attr failed"; unload(); return false;
            }
        }
        boxOut_ = clsOut_ = -1;
        for (int i = 0; i < 2; ++i) {
            if (oa[i].n_dims != 3 || oa[i].dims[2] != 8400) continue;
            if (oa[i].dims[1] == 4) boxOut_ = i;
            else                     clsOut_ = i;
        }
        if (boxOut_ < 0 || clsOut_ < 0) {
            err = "split outputs shape unexpected"; unload(); return false;
        }
        split_ = true; e2e_ = false; generic_ = false; posFirst_ = false;
        nc_ = (int)oa[clsOut_].dims[1];
        if (nc_ <= 0 || nc_ > 256) { err = "bad class count " + std::to_string(nc_); unload(); return false; }
        return true;
    }

    if (out_attr.n_dims != 3) {
        // generic tensor (e.g. tiny op-probe models): accept, no detection decode
        generic_ = true; e2e_ = false; nc_ = 1; posFirst_ = false;
        out_elems_ = 1;
        for (uint32_t i = 0; i < out_attr.n_dims; ++i) out_elems_ *= out_attr.dims[i];
        return true;
    }
    uint32_t d0 = out_attr.dims[0], d1 = out_attr.dims[1], d2 = out_attr.dims[2];

    if (d1 == 300 && d2 == 6) {
        e2e_ = true; nc_ = 1; posFirst_ = false;
    } else if (d2 == 8400) {
        e2e_ = false; posFirst_ = false; nc_ = (int)d1 - 4;   // [1,4+nc,8400]
    } else if (d1 == 8400) {
        e2e_ = false; posFirst_ = true;  nc_ = (int)d2 - 4;   // [1,8400,4+nc]
    } else {
        char buf[128];
        snprintf(buf, sizeof(buf), "unsupported output shape [%u,%u,%u]", d0, d1, d2);
        err = buf; unload(); return false;
    }
    if (nc_ <= 0 || nc_ > 256) { err = "bad class count " + std::to_string(nc_); unload(); return false; }
    return true;
}

void Yolo26Rknn::unload() {
    if (ctx_) { rknn_destroy((rknn_context)ctx_); ctx_ = nullptr; }
}

std::vector<Det> Yolo26Rknn::infer(const uint8_t *nhwc, float confThresh, float nmsThresh) {
    std::vector<Det> dets;
    if (!ctx_ || nhwc == nullptr) return dets;

    auto t0 = std::chrono::steady_clock::now();
    const bool dbg = getenv("DETVIEW_DEBUG") != nullptr;

    rknn_input in;
    memset(&in, 0, sizeof(in));
    in.index = 0;
    in.buf = (void *)nhwc;
    in.size = (uint32_t)(mw_ * mh_ * 3);
    in.pass_through = 0;
    in.type = RKNN_TENSOR_UINT8;
    in.fmt = RKNN_TENSOR_NHWC;
    if (rknn_inputs_set((rknn_context)ctx_, 1, &in) < 0) return dets;
    if (rknn_run((rknn_context)ctx_, nullptr) < 0) return dets;

    if (split_) {
        // [SPLIT] two outputs: boxes [1,4,8400] + scores [1,nc,8400] (post-sigmoid).
        rknn_output outs[2];
        memset(outs, 0, sizeof(outs));
        for (int k = 0; k < 2; ++k) { outs[k].want_float = 1; outs[k].is_prealloc = 0; outs[k].index = k; }
        if (rknn_outputs_get((rknn_context)ctx_, 2, outs, nullptr) < 0) return dets;
        const float *pb = (const float *)outs[boxOut_].buf;
        const float *pc = (const float *)outs[clsOut_].buf;
        const int AN = 8400;
        std::vector<Det> cand;
        float gscore = 0.0f;
        for (int a = 0; a < AN; ++a) {
            int best = -1; float bs = confThresh;
            for (int c = 0; c < nc_; ++c) {
                float s = pc[(size_t)c * AN + a];
                if (s > gscore) gscore = s;
                if (s > bs) { bs = s; best = c; }
            }
            if (best < 0) continue;
            Det d;
            d.x1 = pb[0 * AN + a]; d.y1 = pb[1 * AN + a];
            d.x2 = pb[2 * AN + a]; d.y2 = pb[3 * AN + a];
            d.score = bs; d.cls = best;
            cand.push_back(d);
        }
        lastScoreMax_ = gscore;
        if (dbg) {
            float smin = pc[0], smax = pc[0], ssum = 0;
            for (int k = 0; k < nc_ * AN; ++k) { float v = pc[k]; if (v < smin) smin = v; if (v > smax) smax = v; ssum += v; }
            printf("[SPLIT] nc=%d kept=%zu score min=%.4f max=%.4f mean=%.4f | box0=(%.1f,%.1f,%.1f,%.1f)\n",
                   nc_, cand.size(), smin, smax, ssum / (float)(nc_ * AN),
                   pb[0], pb[1], pb[2], pb[3]);
        }
        dets = nmsClassAware(cand, nmsThresh);
        rknn_outputs_release((rknn_context)ctx_, 2, outs);
        lastMs_ = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
        return dets;
    }

    rknn_output out;
    memset(&out, 0, sizeof(out));
    out.want_float = getenv("DETVIEW_RAW") ? 0 : 1;
    out.is_prealloc = 0;
    out.index = 0;
    if (rknn_outputs_get((rknn_context)ctx_, 1, &out, nullptr) < 0) return dets;

    if (generic_) {
        // dump stats for any-shaped tensor: answers "is this op alive on device?"
        const int8_t *q = (const int8_t *)out.buf;
        const float *pf = (const float *)out.buf;
        if (dbg || true) {
            printf("[PROBE] elems=%d want_float=%d", out_elems_, (int)(getenv("DETVIEW_RAW") ? 0 : 1));
            if (getenv("DETVIEW_RAW")) {
                int nz = 0, mn = 127, mx = -128;
                for (int i = 0; i < out_elems_; ++i) { int v = q[i]; if (v != out_zp_) ++nz; if (v < mn) mn = v; if (v > mx) mx = v; }
                printf(" zp=%d i8_min=%d i8_max=%d nonzero=%d", out_zp_, mn, mx, nz);
            } else {
                float mn = pf[0], mx = pf[0], sum = 0;
                for (int i = 0; i < out_elems_; ++i) { if (pf[i] < mn) mn = pf[i]; if (pf[i] > mx) mx = pf[i]; sum += pf[i]; }
                printf(" f_min=%.5f f_max=%.5f f_mean=%.5f", mn, mx, sum / out_elems_);
            }
            printf("\n");
        }
        rknn_outputs_release((rknn_context)ctx_, 1, &out);
        lastMs_ = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
        return dets;
    }

    if (getenv("DETVIEW_RAW")) {
        // Manual dequant straight from the raw tensor: distinguishes "runtime
        // float conversion broken" from "model output broken".
        const int8_t *q = (const int8_t *)out.buf;
        int nz = 0;
        for (uint32_t i = 0; i < out.size; ++i) if (q[i] != (int8_t)out_zp_) ++nz;
        if (dbg)
            printf("[RAW] out.size=%u zp=%d scale=%.6g nonzero-vs-zp=%d\n",
                   out.size, out_zp_, out_scale_, nz);
        FILE *df = fopen("/tmp/out.i8", "wb");
        if (df) { fwrite(q, 1, out.size, df); fclose(df); }
        if (!e2e_) {
            const int AN = 8400;
            std::vector<Det> cand;
            for (int a = 0; a < AN; ++a) {
                float cx = (q[0 * AN + a] - out_zp_) * out_scale_;
                float cy = (q[1 * AN + a] - out_zp_) * out_scale_;
                float w  = (q[2 * AN + a] - out_zp_) * out_scale_;
                float h  = (q[3 * AN + a] - out_zp_) * out_scale_;
                int best = -1; float bs = confThresh;
                for (int c = 0; c < nc_; ++c) {
                    float s = (q[(4 + c) * AN + a] - out_zp_) * out_scale_;
                    if (s > bs) { bs = s; best = c; }
                }
                if (best < 0) continue;
                Det d; d.x1 = cx - w / 2; d.y1 = cy - h / 2; d.x2 = cx + w / 2; d.y2 = cy + h / 2;
                d.score = bs; d.cls = best; cand.push_back(d);
            }
            dets = nmsClassAware(cand, nmsThresh);
        }
        rknn_outputs_release((rknn_context)ctx_, 1, &out);
        lastMs_ = std::chrono::duration<double, std::milli>(
                      std::chrono::steady_clock::now() - t0).count();
        return dets;
    }

    const float *p = (const float *)out.buf;

    if (dbg && !e2e_) {
        // Per-channel stats: the decisive probe for "scores are exactly zero".
        const int AN = 8400;
        for (int c = 0; c < 4 + nc_ && c < 12; ++c) {
            float mn = p[(size_t)c * AN], mx = mn, sum = 0;
            for (int a = 0; a < AN; ++a) {
                float v = p[(size_t)c * AN + a];
                if (v < mn) mn = v;
                if (v > mx) mx = v;
                sum += v;
            }
            printf("[CH] c%-3d min=%.3f max=%.3f mean=%.3f\n", c, mn, mx, sum / AN);
        }
        float gmx = p[0];
        for (size_t i = 0; i < out.size / 4; ++i) if (p[i] > gmx) gmx = p[i];
        printf("[DBG] out floats=%u  global_max=%.4g\n", out.size / 4, gmx);
    }

    if (e2e_) {
        if (dbg) {
            for (int i = 0; i < 4; ++i) {
                const float *r = p + (size_t)i * 6;
                printf("[E2E] row%d: %.1f %.1f %.1f %.1f score=%.4f cls=%.1f\n",
                       i, r[0], r[1], r[2], r[3], r[4], r[5]);
            }
        }
        float smax = 0;
        for (int i = 0; i < 300; ++i) {
            const float *r = p + (size_t)i * 6;
            float score = r[4];
            int cls = (int)r[5];
            if (score > smax) smax = score;
            if (score >= confThresh && cls >= 0 && cls < nc_) {
                Det d{r[0], r[1], r[2], r[3], score, cls};
                dets.push_back(d);
            }
        }
        lastScoreMax_ = smax;
        dets = nmsClassAware(dets, nmsThresh);   // e2e is NMS-free per spec; cheap safety net
    } else {
        const int AN = 8400;
        std::vector<Det> cand;
        cand.reserve(256);
        float smax = 0;
        for (int a = 0; a < AN; ++a) {
            float cx, cy, w, h;
            const float *scores;
            if (posFirst_) {
                const float *row = p + (size_t)a * (4 + nc_);
                cx = row[0]; cy = row[1]; w = row[2]; h = row[3];
                scores = row + 4;
            } else {
                cx = p[0 * AN + a];
                cy = p[1 * AN + a];
                w  = p[2 * AN + a];
                h  = p[3 * AN + a];
                scores = p + 4 * AN;
            }
            int best = -1; float bs = confThresh;
            for (int c = 0; c < nc_; ++c) {
                float s = posFirst_ ? scores[c] : scores[(size_t)c * AN + a];
                if (s > smax) smax = s;
                if (s > bs) { bs = s; best = c; }
            }
            if (best < 0) continue;
            Det d;
            d.x1 = cx - w * 0.5f; d.y1 = cy - h * 0.5f;
            d.x2 = cx + w * 0.5f; d.y2 = cy + h * 0.5f;
            d.score = bs; d.cls = best;
            cand.push_back(d);
        }
        lastScoreMax_ = smax;
        dets = nmsClassAware(cand, nmsThresh);
    }

    rknn_outputs_release((rknn_context)ctx_, 1, &out);

    std::chrono::duration<double, std::milli> el = std::chrono::steady_clock::now() - t0;
    lastMs_ = el.count();
    return dets;
}

static float iou(const Det &a, const Det &b) {
    float ix1 = std::max(a.x1, b.x1), iy1 = std::max(a.y1, b.y1);
    float ix2 = std::min(a.x2, b.x2), iy2 = std::min(a.y2, b.y2);
    float iw = std::max(0.0f, ix2 - ix1), ih = std::max(0.0f, iy2 - iy1);
    float inter = iw * ih;
    float areaA = std::max(0.0f, a.x2 - a.x1) * std::max(0.0f, a.y2 - a.y1);
    float areaB = std::max(0.0f, b.x2 - b.x1) * std::max(0.0f, b.y2 - b.y1);
    float uni = areaA + areaB - inter;
    return uni > 0 ? inter / uni : 0.0f;
}

std::vector<Det> nmsClassAware(std::vector<Det> dets, float iouThresh) {
    std::sort(dets.begin(), dets.end(),
              [](const Det &a, const Det &b) { return a.score > b.score; });
    std::vector<Det> keep;
    std::vector<bool> suppressed(dets.size(), false);
    for (size_t i = 0; i < dets.size(); ++i) {
        if (suppressed[i]) continue;
        keep.push_back(dets[i]);
        for (size_t j = i + 1; j < dets.size(); ++j) {
            if (suppressed[j] || dets[j].cls != dets[i].cls) continue;
            if (iou(dets[i], dets[j]) > iouThresh) suppressed[j] = true;
        }
    }
    return keep;
}
