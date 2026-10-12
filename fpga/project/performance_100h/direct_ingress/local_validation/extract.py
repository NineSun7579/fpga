"""Extract exact production bytes; no rewritten gate logic in the harness."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parent
source = root.parent / 'src/main.cpp'
data = source.read_bytes()
records = []

def take(name, start, end):
    lo = data.index(start)
    hi = data.index(end, lo) + len(end)
    chunk = data[lo:hi]
    records.append(dict(name=name, first_line=data[:lo].count(b'\n') + 1,
                        bytes=len(chunk), sha256=hashlib.sha256(chunk).hexdigest()))
    (root / (name + '.inc')).write_bytes(chunk + b'\n')

for name, start in [('submit', b'    void submit(const QImage &img'),
                    ('clear_pending', b'    void clearPending()'),
                    ('stop', b'    void stop() {\n        {'),
                    ('close_ingress', b'    void closeIngress('),
                    ('open_ingress', b'    void openIngress()')]:
    take(name, start, b'\n    }')
take('connection', b'        connect(m_vision, &VisionPipeline::inferenceRequested, this,',
     b'        }, Qt::DirectConnection);')
take('dequeue', b'            QImage frame;\n            const bool hadPending', b'            lock.unlock();')
take('wait_predicate', b'            if (!m_hasPending && !m_modelChanged && !m_stop)',
     b'                break;')
(root / 'production_manifest.json').write_text(json.dumps(dict(
    source=str(source), source_sha256=hashlib.sha256(data).hexdigest(),
    extracts=records), indent=2) + '\n', encoding='utf-8')
print('EXTRACTION_PASS source_sha256=' + hashlib.sha256(data).hexdigest())
