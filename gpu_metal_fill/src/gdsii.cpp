#include "metalfill/gdsii.hpp"

#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <stdexcept>

namespace mf {
namespace {

// ---- GDSII record identifiers (rectype << 8 | datatype) --------------------
constexpr uint8_t RT_HEADER = 0x00, RT_BGNLIB = 0x01, RT_LIBNAME = 0x02;
constexpr uint8_t RT_UNITS = 0x03, RT_ENDLIB = 0x04, RT_BGNSTR = 0x05;
constexpr uint8_t RT_STRNAME = 0x06, RT_ENDSTR = 0x07, RT_BOUNDARY = 0x08;
constexpr uint8_t RT_LAYER = 0x0D, RT_DATATYPE = 0x0E, RT_XY = 0x10;
constexpr uint8_t RT_ENDEL = 0x11, RT_BOX = 0x2D, RT_BOXTYPE = 0x2E;

constexpr uint8_t DT_NODATA = 0x00, DT_INT2 = 0x02, DT_INT4 = 0x03;
constexpr uint8_t DT_REAL8 = 0x05, DT_STR = 0x06;

// ---- big-endian helpers ----------------------------------------------------
void put_u16(std::ofstream& os, uint16_t v) {
    char b[2] = {char((v >> 8) & 0xFF), char(v & 0xFF)};
    os.write(b, 2);
}
void put_i16(std::ofstream& os, int16_t v) { put_u16(os, static_cast<uint16_t>(v)); }
void put_i32(std::ofstream& os, int32_t v) {
    char b[4] = {char((v >> 24) & 0xFF), char((v >> 16) & 0xFF), char((v >> 8) & 0xFF),
                 char(v & 0xFF)};
    os.write(b, 4);
}

uint16_t get_u16(const uint8_t* p) { return (uint16_t(p[0]) << 8) | p[1]; }
int32_t get_i32(const uint8_t* p) {
    return int32_t((uint32_t(p[0]) << 24) | (uint32_t(p[1]) << 16) | (uint32_t(p[2]) << 8) |
                   uint32_t(p[3]));
}

// GDSII 8-byte real: sign (bit7), 7-bit excess-64 base-16 exponent, 56-bit mantissa.
void put_real8(std::ofstream& os, double v) {
    uint8_t out[8] = {0};
    if (v != 0.0) {
        bool neg = v < 0;
        double d = std::fabs(v);
        int exp = 64;
        while (d >= 1.0) { d /= 16.0; ++exp; }
        while (d < 1.0 / 16.0) { d *= 16.0; --exp; }
        // d now in [1/16, 1); build 56-bit mantissa.
        uint64_t mant = static_cast<uint64_t>(std::llround(d * static_cast<double>(1ULL << 56)));
        out[0] = static_cast<uint8_t>((neg ? 0x80 : 0x00) | (exp & 0x7F));
        for (int i = 7; i >= 1; --i) {
            out[i] = static_cast<uint8_t>(mant & 0xFF);
            mant >>= 8;
        }
    }
    os.write(reinterpret_cast<char*>(out), 8);
}

double get_real8(const uint8_t* p) {
    bool neg = (p[0] & 0x80) != 0;
    int exp = (p[0] & 0x7F) - 64;
    uint64_t mant = 0;
    for (int i = 1; i < 8; ++i) mant = (mant << 8) | p[i];
    double d = static_cast<double>(mant) / static_cast<double>(1ULL << 56);
    d *= std::pow(16.0, exp);
    return neg ? -d : d;
}

void write_record(std::ofstream& os, uint8_t rectype, uint8_t datatype, const char* data,
                  uint16_t data_len) {
    uint16_t total = static_cast<uint16_t>(4 + data_len);
    put_u16(os, total);
    char hdr[2] = {char(rectype), char(datatype)};
    os.write(hdr, 2);
    if (data_len) os.write(data, data_len);
}

void write_str(std::ofstream& os, uint8_t rectype, const std::string& s) {
    std::string p = s;
    if (p.size() & 1) p.push_back('\0');  // pad to even length
    write_record(os, rectype, DT_STR, p.data(), static_cast<uint16_t>(p.size()));
}

}  // namespace

Layout read_gds(const std::string& path) {
    std::ifstream is(path, std::ios::binary);
    if (!is) throw std::runtime_error("cannot open GDS for read: " + path);

    Layout layout;
    Polygon cur;
    bool in_elem = false;
    bool is_box = false;

    while (true) {
        uint8_t hdr[4];
        is.read(reinterpret_cast<char*>(hdr), 4);
        if (is.gcount() == 0) break;  // clean EOF
        if (is.gcount() != 4) throw std::runtime_error("truncated GDS record header");

        uint16_t total = get_u16(hdr);
        uint8_t rectype = hdr[2];
        uint8_t datatype = hdr[3];
        if (total < 4) throw std::runtime_error("invalid GDS record length");
        int data_len = total - 4;
        std::vector<uint8_t> data(data_len);
        if (data_len) {
            is.read(reinterpret_cast<char*>(data.data()), data_len);
            if (is.gcount() != data_len) throw std::runtime_error("truncated GDS record body");
        }

        switch (rectype) {
            case RT_UNITS:
                if (data_len >= 16) {
                    layout.user_units_per_dbu = get_real8(data.data());
                    layout.meters_per_dbu = get_real8(data.data() + 8);
                }
                break;
            case RT_LIBNAME:
                layout.lib_name.assign(reinterpret_cast<char*>(data.data()), data_len);
                break;
            case RT_STRNAME:
                layout.cell_name.assign(reinterpret_cast<char*>(data.data()), data_len);
                if (!layout.cell_name.empty() && layout.cell_name.back() == '\0')
                    layout.cell_name.pop_back();
                break;
            case RT_BOUNDARY:
                cur = Polygon{};
                in_elem = true;
                is_box = false;
                break;
            case RT_BOX:
                cur = Polygon{};
                in_elem = true;
                is_box = true;
                break;
            case RT_LAYER:
                if (in_elem && data_len >= 2) cur.layer = int(int16_t(get_u16(data.data())));
                break;
            case RT_DATATYPE:
            case RT_BOXTYPE:
                if (in_elem && data_len >= 2) cur.datatype = int(int16_t(get_u16(data.data())));
                break;
            case RT_XY:
                if (in_elem) {
                    int npairs = data_len / 8;
                    cur.pts.clear();
                    cur.pts.reserve(npairs);
                    for (int i = 0; i < npairs; ++i) {
                        dbu x = get_i32(data.data() + i * 8);
                        dbu y = get_i32(data.data() + i * 8 + 4);
                        cur.pts.push_back({x, y});
                    }
                    // Drop the closing duplicate vertex if present.
                    if (cur.pts.size() > 1 && cur.pts.front().x == cur.pts.back().x &&
                        cur.pts.front().y == cur.pts.back().y)
                        cur.pts.pop_back();
                }
                break;
            case RT_ENDEL:
                if (in_elem && cur.pts.size() >= 3) layout.polygons.push_back(cur);
                in_elem = false;
                is_box = false;
                break;
            default:
                break;  // ignore HEADER/BGNLIB/PATH/SREF/etc.
        }
        (void)datatype;
        (void)is_box;
    }
    return layout;
}

void write_gds(const std::string& path, const Layout& layout) {
    std::ofstream os(path, std::ios::binary);
    if (!os) throw std::runtime_error("cannot open GDS for write: " + path);

    // HEADER (version 600)
    char ver[2] = {0x02, 0x58};
    write_record(os, RT_HEADER, DT_INT2, ver, 2);

    // BGNLIB (24 bytes of timestamps, all zero)
    char zeros[24] = {0};
    write_record(os, RT_BGNLIB, DT_INT2, zeros, 24);
    write_str(os, RT_LIBNAME, layout.lib_name);

    // UNITS: [user units per dbu, meters per dbu]
    put_u16(os, 20);  // 4 header + 16 payload
    os.put(char(RT_UNITS));
    os.put(char(DT_REAL8));
    put_real8(os, layout.user_units_per_dbu);
    put_real8(os, layout.meters_per_dbu);

    // BGNSTR
    write_record(os, RT_BGNSTR, DT_INT2, zeros, 24);
    write_str(os, RT_STRNAME, layout.cell_name);

    for (const auto& poly : layout.polygons) {
        if (poly.pts.size() < 3) continue;
        write_record(os, RT_BOUNDARY, DT_NODATA, nullptr, 0);
        put_u16(os, 6);  // LAYER record
        os.put(char(RT_LAYER));
        os.put(char(DT_INT2));
        put_i16(os, static_cast<int16_t>(poly.layer));
        put_u16(os, 6);  // DATATYPE record
        os.put(char(RT_DATATYPE));
        os.put(char(DT_INT2));
        put_i16(os, static_cast<int16_t>(poly.datatype));

        // XY: points + closing vertex.
        int npts = static_cast<int>(poly.pts.size()) + 1;
        uint16_t xy_len = static_cast<uint16_t>(npts * 8);
        put_u16(os, static_cast<uint16_t>(4 + xy_len));
        os.put(char(RT_XY));
        os.put(char(DT_INT4));
        for (const auto& p : poly.pts) {
            put_i32(os, static_cast<int32_t>(p.x));
            put_i32(os, static_cast<int32_t>(p.y));
        }
        put_i32(os, static_cast<int32_t>(poly.pts.front().x));
        put_i32(os, static_cast<int32_t>(poly.pts.front().y));

        write_record(os, RT_ENDEL, DT_NODATA, nullptr, 0);
    }

    write_record(os, RT_ENDSTR, DT_NODATA, nullptr, 0);
    write_record(os, RT_ENDLIB, DT_NODATA, nullptr, 0);
}

}  // namespace mf
