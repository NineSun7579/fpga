#pragma once
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstring>
#include <vector>
#include "sdk/rknn_api.h"
#include "frozen/vision_types.h"
static const int MODEL_W = 640;
static const int MODEL_H = 640;
static const size_t MODEL_SIZE = (size_t)MODEL_W * MODEL_H * 3;
static const float CONF_THRESH = 0.25f;
static const float IOU_THRESH = 0.45f;
static void rgb565ToRgb888Line(const uint8_t *src, int pixels, uint8_t *dst) {
    const uint16_t *s = reinterpret_cast<const uint16_t *>(src);
    for (int i = 0; i < pixels; i++) {
        const uint16_t v = s[i];
        const uint8_t r5 = (v >> 11) & 0x1F;
        const uint8_t g6 = (v >> 5) & 0x3F;
        const uint8_t b5 = v & 0x1F;
        dst[3 * i + 0] = (r5 << 3) | (r5 >> 2);
        dst[3 * i + 1] = (g6 << 2) | (g6 >> 4);
        dst[3 * i + 2] = (b5 << 3) | (b5 >> 2);
    }
}

class FrozenDecoder {
public:
    static float sigmoidf(float x) { return 1.0f / (1.0f + std::exp(-x)); }

    struct CandD {
        float score, x1, y1, x2, y2;
        int cls;
    };

    static void nmsAppend(QVector<Detection> &dets, std::vector<CandD> &cands) {
        std::sort(cands.begin(), cands.end(),
                  [](const CandD &a, const CandD &b) { return a.score > b.score; });
        std::vector<bool> removed(cands.size(), false);
        for (size_t i = 0; i < cands.size(); i++) {
            if (removed[i])
                continue;
            const CandD &a = cands[i];
            Detection detection;
            detection.cls = a.cls; detection.score = a.score;
            detection.x1 = a.x1; detection.y1 = a.y1; detection.x2 = a.x2; detection.y2 = a.y2;
            dets.append(detection);
            for (size_t j = i + 1; j < cands.size(); j++) {
                if (removed[j])
                    continue;
                const CandD &b = cands[j];
                const float xx1 = std::max(a.x1, b.x1);
                const float yy1 = std::max(a.y1, b.y1);
                const float xx2 = std::min(a.x2, b.x2);
                const float yy2 = std::min(a.y2, b.y2);
                const float w = std::max(0.0f, xx2 - xx1);
                const float h = std::max(0.0f, yy2 - yy1);
                const float inter = w * h;
                const float ai = (a.x2 - a.x1) * (a.y2 - a.y1);
                const float bj = (b.x2 - b.x1) * (b.y2 - b.y1);
                if (inter / (ai + bj - inter + 1e-6f) > IOU_THRESH)
                    removed[j] = true;
            }
        }
    }

    /* zoo 风格 6 输出（DFL 未在模型内解码）：3x[1,4*bins,H,W] + 3x[1,nc,H,W]
       命中该布局返回 true；否则返回 false 交回原有解码路径 */
    bool tryDecodeDfl(const std::vector<rknn_output> &outs,
                      const std::vector<rknn_tensor_attr> &attrs, float confThresh,
                      QVector<Detection> &dets) {
        struct Item {
            const float *data;
            int ch, h, w;
        };
        std::vector<Item> items;
        for (size_t i = 0; i < outs.size(); i++) {
            if (attrs[i].n_dims != 4)
                continue;
            items.push_back({(const float *)outs[i].buf, (int)attrs[i].dims[1],
                             (int)attrs[i].dims[2], (int)attrs[i].dims[3]});
        }

        struct Scale {
            const float *box;
            const float *cls;
            int h, w, nc, bins;
        };
        std::vector<Scale> scales;
        /* 按 (h,w) 配对：同一尺度下 cls 的通道数等于/最接近 m_nc，另一路即 box，
           bins 由 box 通道数推出（4*bins）。不写死 64/16，reg_max 变了也不用改代码。 */
        for (const Item &a : items) {
            const Item *peer = nullptr;
            for (const Item &b : items) {
                if (&b == &a || b.h != a.h || b.w != a.w)
                    continue;
                if (!peer || std::abs(b.ch - m_nc) < std::abs(peer->ch - m_nc))
                    peer = &b;
            }
            if (!peer)
                continue;
            /* 只从 box 那一侧建条目，避免同一尺度被登记两次 */
            if (std::abs(a.ch - m_nc) <= std::abs(peer->ch - m_nc))
                continue;
            if (a.ch % 4 != 0 || a.ch / 4 < 1 || a.ch / 4 > 32)
                continue;
            scales.push_back({a.data, peer->data, a.h, a.w, peer->ch, a.ch / 4});
        }
        if (scales.empty())
            return false;

        bool sigmoid = false;
        {
            const Scale &sc = scales[0];
            float mx = -1e9f, mn = 1e9f;
            const int n = std::min(sc.h * sc.w, 2000);
            for (int i = 0; i < n; i++) {
                mx = std::max(mx, sc.cls[i]);
                mn = std::min(mn, sc.cls[i]);
            }
            sigmoid = (mx > 1.5f || mn < -0.5f);
        }

        struct AC {
            float score;
            int cls, s, y, x;
        };
        std::vector<AC> cands;
        for (int si = 0; si < (int)scales.size(); si++) {
            const Scale &sc = scales[si];
            const int plane = sc.h * sc.w;
            const int nc = std::min(sc.nc, m_nc > 0 ? m_nc : sc.nc);
            for (int y = 0; y < sc.h; y++)
                for (int x = 0; x < sc.w; x++) {
                    const int off = y * sc.w + x;
                    float best = -1.0f;
                    int bestCls = -1;
                    for (int c = 0; c < nc; c++) {
                        float v = sc.cls[(size_t)c * plane + off];
                        if (sigmoid)
                            v = sigmoidf(v);
                        if (v > best) {
                            best = v;
                            bestCls = c;
                        }
                    }
                    if (best >= confThresh && bestCls >= 0)
                        cands.push_back({best, bestCls, si, y, x});
                }
        }
        if (cands.empty())
            return true;
        std::sort(cands.begin(), cands.end(),
                  [](const AC &a, const AC &b) { return a.score > b.score; });
        if (cands.size() > 300)
            cands.resize(300);

        std::vector<CandD> boxes;
        boxes.reserve(cands.size());
        for (const AC &c : cands) {
            const Scale &sc = scales[c.s];
            const int plane = sc.h * sc.w;
            const int stride = MODEL_W / sc.w;
            const size_t base = (size_t)c.y * sc.w + c.x;
            float d[4];
            for (int k = 0; k < 4; k++) {
                const float *p = sc.box + (size_t)(k * sc.bins) * plane + base;
                float mx = p[0];
                for (int b = 1; b < sc.bins; b++)
                    mx = std::max(mx, p[(size_t)b * plane]);
                float e[32];
                const int nb = std::min(sc.bins, 32);
                float sum = 0;
                for (int b = 0; b < nb; b++) {
                    e[b] = std::exp(p[(size_t)b * plane] - mx);
                    sum += e[b];
                }
                float res = 0;
                for (int b = 0; b < nb; b++)
                    res += b * e[b] / (sum + 1e-9f);
                d[k] = res;
            }
            const float cx = (c.x + 0.5f) * stride;
            const float cy = (c.y + 0.5f) * stride;
            boxes.push_back({c.score, cx - d[0] * stride, cy - d[1] * stride,
                             cx + d[2] * stride, cy + d[3] * stride, c.cls});
        }
        nmsAppend(dets, boxes);
        return true;
    }

    QVector<Detection> decode(const std::vector<rknn_output> &outs,
                              const std::vector<rknn_tensor_attr> &attrs) {
        QVector<Detection> dets;
        const float confThresh = m_conf.load();
        if (outs.empty())
            return dets;
        if (tryDecodeDfl(outs, attrs, confThresh, dets))
            return dets;
        const float *boxData = nullptr;
        int boxN = 0;
        const float *combined = nullptr;
        int combinedC = 0, combinedN = 0;
        const float *clsTensor = nullptr;
        int clsRows = 0, clsN = 0, clsRowOffset = 0;
        bool e2e = false;
        int e2eN = 0;

        // pass 1: locate the e2e [N,6] tensor, the 4-row box tensor, or a fused box+cls tensor
        for (size_t i = 0; i < outs.size(); i++) {
            if (attrs[i].n_dims != 3)
                continue;
            const float *data = (const float *)outs[i].buf;
            if (attrs[i].dims[2] == 6) {
                e2e = true;
                e2eN = attrs[i].dims[1];
                boxData = data;
            } else if (attrs[i].dims[1] == 4 && !boxData) {
                boxData = data;
                boxN = attrs[i].dims[2];
            } else if (attrs[i].dims[1] > 4) {
                combined = data;
                combinedC = attrs[i].dims[1];
                combinedN = attrs[i].dims[2];
            }
        }
        // pass 2: separate scores tensor sharing the anchor count (any class count)
        if (!e2e && boxData) {
            for (size_t i = 0; i < outs.size(); i++) {
                if (attrs[i].n_dims != 3)
                    continue;
                const float *data = (const float *)outs[i].buf;
                if (data == boxData || (int)attrs[i].dims[2] != boxN)
                    continue;
                clsTensor = data;
                clsRows = attrs[i].dims[1];
                clsN = attrs[i].dims[2];
                clsRowOffset = 0;
                break;
            }
        }
        if (!e2e && !clsTensor && combined && combinedC > 4) {
            boxData = combined;
            boxN = combinedN;
            clsTensor = combined;
            clsRows = combinedC - 4;
            clsN = combinedN;
            clsRowOffset = 4;
        }
        if (e2e && boxData) {
            for (int i = 0; i < e2eN; i++) {
                const float *r = boxData + (size_t)i * 6;
                if (r[4] < confThresh)
                    continue;
                Detection d;
                d.x1 = r[0];
                d.y1 = r[1];
                d.x2 = r[2];
                d.y2 = r[3];
                d.score = r[4];
                d.cls = (int)r[5];
                dets.append(d);
            }
            return dets;
        }
        if (!boxData || boxN <= 0 || !clsTensor || clsRows <= 0)
            return dets;

        const int nClasses = std::min(clsRows, m_nc > 0 ? m_nc : clsRows);

        bool sigmoid = false;
        {
            float mx = -1e9f, mn = 1e9f;
            for (int i = 0; i < clsN && i < 1000; i++) {
                const float v = clsTensor[(size_t)clsRowOffset * clsN + i];
                mx = std::max(mx, v);
                mn = std::min(mn, v);
            }
            sigmoid = (mx > 1.5f || mn < -0.5f);
        }

        std::vector<CandD> cands;
        for (int i = 0; i < boxN; i++) {
            float best = -1.0f;
            int bestCls = -1;
            for (int c = 0; c < nClasses; c++) {
                float s = clsTensor[(size_t)(clsRowOffset + c) * clsN + i];
                if (sigmoid)
                    s = sigmoidf(s);
                if (s > best) {
                    best = s;
                    bestCls = c;
                }
            }
            if (best < confThresh || bestCls < 0)
                continue;
            const float a0 = boxData[i];
            const float a1 = boxData[boxN + i];
            const float a2 = boxData[2 * boxN + i];
            const float a3 = boxData[3 * boxN + i];
            float x1, y1, x2, y2;
            if (m_xyxy) {
                x1 = a0;
                y1 = a1;
                x2 = a2;
                y2 = a3;
            } else {
                x1 = a0 - a2 / 2;
                y1 = a1 - a3 / 2;
                x2 = a0 + a2 / 2;
                y2 = a1 + a3 / 2;
            }
            cands.push_back({best, x1, y1, x2, y2, bestCls});
        }
        nmsAppend(dets, cands);
        return dets;
    }

private:
    int m_nc = 3;
    bool m_xyxy = false;
    std::atomic<float> m_conf{0.25f};
};
