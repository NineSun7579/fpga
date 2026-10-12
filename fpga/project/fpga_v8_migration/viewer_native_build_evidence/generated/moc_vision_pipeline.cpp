/****************************************************************************
** Meta object code from reading C++ file 'vision_pipeline.h'
**
** Created by: The Qt Meta Object Compiler version 67 (Qt 5.15.8)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "../../src/vision_pipeline.h"
#include <QtCore/qbytearray.h>
#include <QtCore/qmetatype.h>
#include <QtCore/QVector>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'vision_pipeline.h' doesn't include <QObject>."
#elif Q_MOC_OUTPUT_REVISION != 67
#error "This file was generated using the moc from 5.15.8. It"
#error "cannot be used with the include files from this version of Qt."
#error "(The moc has changed too much.)"
#endif

QT_BEGIN_MOC_NAMESPACE
QT_WARNING_PUSH
QT_WARNING_DISABLE_DEPRECATED
struct qt_meta_stringdata_VisionPipeline_t {
    QByteArrayData data[18];
    char stringdata0[199];
};
#define QT_MOC_LITERAL(idx, ofs, len) \
    Q_STATIC_BYTE_ARRAY_DATA_HEADER_INITIALIZER_WITH_OFFSET(len, \
    qptrdiff(offsetof(qt_meta_stringdata_VisionPipeline_t, stringdata0) + ofs \
        - idx * sizeof(QByteArrayData)) \
    )
static const qt_meta_stringdata_VisionPipeline_t qt_meta_stringdata_VisionPipeline = {
    {
QT_MOC_LITERAL(0, 0, 14), // "VisionPipeline"
QT_MOC_LITERAL(1, 15, 18), // "inferenceRequested"
QT_MOC_LITERAL(2, 34, 0), // ""
QT_MOC_LITERAL(3, 35, 11), // "VisionFrame"
QT_MOC_LITERAL(4, 47, 5), // "frame"
QT_MOC_LITERAL(5, 53, 11), // "tracksReady"
QT_MOC_LITERAL(6, 65, 9), // "modelPath"
QT_MOC_LITERAL(7, 75, 16), // "sourceGeneration"
QT_MOC_LITERAL(8, 92, 7), // "frameId"
QT_MOC_LITERAL(9, 100, 18), // "QVector<Detection>"
QT_MOC_LITERAL(10, 119, 10), // "detections"
QT_MOC_LITERAL(11, 130, 10), // "matchingMs"
QT_MOC_LITERAL(12, 141, 11), // "stereoReady"
QT_MOC_LITERAL(13, 153, 11), // "leftFrameId"
QT_MOC_LITERAL(14, 165, 9), // "disparity"
QT_MOC_LITERAL(15, 175, 6), // "status"
QT_MOC_LITERAL(16, 182, 11), // "diagnostics"
QT_MOC_LITERAL(17, 194, 4) // "text"

    },
    "VisionPipeline\0inferenceRequested\0\0"
    "VisionFrame\0frame\0tracksReady\0modelPath\0"
    "sourceGeneration\0frameId\0QVector<Detection>\0"
    "detections\0matchingMs\0stereoReady\0"
    "leftFrameId\0disparity\0status\0diagnostics\0"
    "text"
};
#undef QT_MOC_LITERAL

static const uint qt_meta_data_VisionPipeline[] = {

 // content:
       8,       // revision
       0,       // classname
       0,    0, // classinfo
       4,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       4,       // signalCount

 // signals: name, argc, parameters, tag, flags
       1,    1,   34,    2, 0x06 /* Public */,
       5,    5,   37,    2, 0x06 /* Public */,
      12,    4,   48,    2, 0x06 /* Public */,
      16,    1,   57,    2, 0x06 /* Public */,

 // signals: parameters
    QMetaType::Void, 0x80000000 | 3,    4,
    QMetaType::Void, QMetaType::QString, QMetaType::Int, QMetaType::ULongLong, 0x80000000 | 9, QMetaType::Double,    6,    7,    8,   10,   11,
    QMetaType::Void, QMetaType::Int, QMetaType::ULongLong, QMetaType::QImage, QMetaType::QString,    7,   13,   14,   15,
    QMetaType::Void, QMetaType::QString,   17,

       0        // eod
};

void VisionPipeline::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<VisionPipeline *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->inferenceRequested((*reinterpret_cast< VisionFrame(*)>(_a[1]))); break;
        case 1: _t->tracksReady((*reinterpret_cast< QString(*)>(_a[1])),(*reinterpret_cast< int(*)>(_a[2])),(*reinterpret_cast< quint64(*)>(_a[3])),(*reinterpret_cast< QVector<Detection>(*)>(_a[4])),(*reinterpret_cast< double(*)>(_a[5]))); break;
        case 2: _t->stereoReady((*reinterpret_cast< int(*)>(_a[1])),(*reinterpret_cast< quint64(*)>(_a[2])),(*reinterpret_cast< QImage(*)>(_a[3])),(*reinterpret_cast< QString(*)>(_a[4]))); break;
        case 3: _t->diagnostics((*reinterpret_cast< QString(*)>(_a[1]))); break;
        default: ;
        }
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        switch (_id) {
        default: *reinterpret_cast<int*>(_a[0]) = -1; break;
        case 0:
            switch (*reinterpret_cast<int*>(_a[1])) {
            default: *reinterpret_cast<int*>(_a[0]) = -1; break;
            case 0:
                *reinterpret_cast<int*>(_a[0]) = qRegisterMetaType< VisionFrame >(); break;
            }
            break;
        case 1:
            switch (*reinterpret_cast<int*>(_a[1])) {
            default: *reinterpret_cast<int*>(_a[0]) = -1; break;
            case 3:
                *reinterpret_cast<int*>(_a[0]) = qRegisterMetaType< QVector<Detection> >(); break;
            }
            break;
        }
    } else if (_c == QMetaObject::IndexOfMethod) {
        int *result = reinterpret_cast<int *>(_a[0]);
        {
            using _t = void (VisionPipeline::*)(VisionFrame );
            if (*reinterpret_cast<_t *>(_a[1]) == static_cast<_t>(&VisionPipeline::inferenceRequested)) {
                *result = 0;
                return;
            }
        }
        {
            using _t = void (VisionPipeline::*)(QString , int , quint64 , QVector<Detection> , double );
            if (*reinterpret_cast<_t *>(_a[1]) == static_cast<_t>(&VisionPipeline::tracksReady)) {
                *result = 1;
                return;
            }
        }
        {
            using _t = void (VisionPipeline::*)(int , quint64 , QImage , QString );
            if (*reinterpret_cast<_t *>(_a[1]) == static_cast<_t>(&VisionPipeline::stereoReady)) {
                *result = 2;
                return;
            }
        }
        {
            using _t = void (VisionPipeline::*)(QString );
            if (*reinterpret_cast<_t *>(_a[1]) == static_cast<_t>(&VisionPipeline::diagnostics)) {
                *result = 3;
                return;
            }
        }
    }
}

QT_INIT_METAOBJECT const QMetaObject VisionPipeline::staticMetaObject = { {
    QMetaObject::SuperData::link<QThread::staticMetaObject>(),
    qt_meta_stringdata_VisionPipeline.data,
    qt_meta_data_VisionPipeline,
    qt_static_metacall,
    nullptr,
    nullptr
} };


const QMetaObject *VisionPipeline::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *VisionPipeline::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_VisionPipeline.stringdata0))
        return static_cast<void*>(this);
    return QThread::qt_metacast(_clname);
}

int VisionPipeline::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QThread::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 4)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 4;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 4)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 4;
    }
    return _id;
}

// SIGNAL 0
void VisionPipeline::inferenceRequested(VisionFrame _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 0, _a);
}

// SIGNAL 1
void VisionPipeline::tracksReady(QString _t1, int _t2, quint64 _t3, QVector<Detection> _t4, double _t5)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))), const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t2))), const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t3))), const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t4))), const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t5))) };
    QMetaObject::activate(this, &staticMetaObject, 1, _a);
}

// SIGNAL 2
void VisionPipeline::stereoReady(int _t1, quint64 _t2, QImage _t3, QString _t4)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))), const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t2))), const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t3))), const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t4))) };
    QMetaObject::activate(this, &staticMetaObject, 2, _a);
}

// SIGNAL 3
void VisionPipeline::diagnostics(QString _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 3, _a);
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
