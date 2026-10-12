#include "infer_age.h"
int main() {
    const tdm::InferAge frame{123, 7, 2, 456, 1000};
    tdm::inferAgeEvent("capture_RAW_DMA_complete", frame, 1000);
    tdm::inferAgeEvent("request", frame, 1120);
}
