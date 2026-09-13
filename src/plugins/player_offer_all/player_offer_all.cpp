#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <fstream>
#include <string>
#include <unordered_map>

namespace {

constexpr std::uintptr_t kOfferAllHandlerRva = 0x4FC890;
constexpr std::uintptr_t kListCountRva       = 0x918600;
constexpr std::uintptr_t kListGetValueRva    = 0x9189A0;
constexpr std::uintptr_t kValidateClubRva    = 0x4FDA10;
constexpr std::uintptr_t kExecuteOfferRva    = 0x4FC8D0;
constexpr std::uintptr_t kRefreshRva         = 0x4FD3C0;

constexpr unsigned char kExpectedHandler[] = {
    0x56, 0x8B, 0xF1, 0x8B, 0x86, 0xB8, 0x04, 0x00,
    0x00, 0x25, 0xFF, 0xFF, 0xFF, 0x00, 0x50, 0xE8
};

using ListCountFn = int (__thiscall *)(void*);
using ListGetValueFn = std::uint32_t (__thiscall *)(void*, int, int);
using ValidateClubFn = bool (__thiscall *)(void*, std::uint32_t*, bool);
using ExecuteOfferFn = int (__thiscall *)(void*, std::uint32_t*);
using RefreshFn = void (__thiscall *)(void*);

HMODULE g_module = nullptr;
std::uintptr_t g_game_base = 0;
volatile LONG g_running = 0;
std::unordered_map<std::uint32_t, std::wstring> g_club_names;

std::wstring Utf8ToWide(const std::string& value) {
    if (value.empty()) return {};
    const int size = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS,
        value.data(), static_cast<int>(value.size()), nullptr, 0);
    if (size <= 0) return {};
    std::wstring output(static_cast<size_t>(size), L'\0');
    MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
        static_cast<int>(value.size()), output.data(), size);
    return output;
}

void LoadClubNames() {
    char path[MAX_PATH]{};
    if (!GetModuleFileNameA(g_module, path, MAX_PATH)) return;
    char* slash = std::strrchr(path, '\\');
    if (!slash) return;
    strcpy_s(slash + 1, MAX_PATH - static_cast<size_t>(slash + 1 - path),
        "FM27.PlayerOfferAll.clubs.csv");
    std::ifstream input(path, std::ios::binary);
    std::string line;
    while (std::getline(input, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        const size_t separator = line.find('|');
        if (separator == std::string::npos || line.compare(0, separator, "club_id") == 0) continue;
        try {
            const auto id = static_cast<std::uint32_t>(std::stoul(line.substr(0, separator)));
            std::wstring name = Utf8ToWide(line.substr(separator + 1));
            if (id && !name.empty()) g_club_names.emplace(id, std::move(name));
        } catch (...) {
            // A malformed optional label row must never disable the offer action.
        }
    }
}

void WriteLog(const char* message) {
    char module_path[MAX_PATH]{};
    if (!GetModuleFileNameA(g_module, module_path, MAX_PATH)) return;
    char* slash = std::strrchr(module_path, '\\');
    if (!slash) return;
    strcpy_s(slash + 1, MAX_PATH - static_cast<size_t>(slash + 1 - module_path),
        "FM27.PlayerOfferAll.log");
    FILE* file = nullptr;
    if (fopen_s(&file, module_path, "a") == 0 && file) {
        SYSTEMTIME now{};
        GetLocalTime(&now);
        std::fprintf(file, "%04u-%02u-%02u %02u:%02u:%02u %s\n",
            now.wYear, now.wMonth, now.wDay, now.wHour, now.wMinute, now.wSecond, message);
        std::fclose(file);
    }
}

void RunOfferAll(void* self) {
        auto list_count = reinterpret_cast<ListCountFn>(g_game_base + kListCountRva);
        auto list_value = reinterpret_cast<ListGetValueFn>(g_game_base + kListGetValueRva);
        auto validate = reinterpret_cast<ValidateClubFn>(g_game_base + kValidateClubRva);
        auto execute = reinterpret_cast<ExecuteOfferFn>(g_game_base + kExecuteOfferRva);
        auto refresh = reinterpret_cast<RefreshFn>(g_game_base + kRefreshRva);
        void* list = reinterpret_cast<void*>(reinterpret_cast<unsigned char*>(self) + 0x4FC);

        std::uint32_t clubs[512]{};
        int club_count = 0;
        int rows = list_count(list);
        if (rows < 0) rows = 0;
        if (rows > 512) rows = 512;

        // Freeze the visible list before offers can remove or recolor rows.
        for (int row = 0; row < rows; ++row) {
            const std::uint32_t club = list_value(list, row, 1);
            if (!club) continue;
            bool duplicate = false;
            for (int i = 0; i < club_count; ++i) {
                if (clubs[i] == club) { duplicate = true; break; }
            }
            if (!duplicate) clubs[club_count++] = club;
        }

        int interested = 0;
        int not_interested = 0;
        int not_possible = 0;
        for (int i = 0; i < club_count; ++i) {
            std::uint32_t club = clubs[i];
            // Silent validation uses the game's normal eligibility checks without
            // opening one modal dialog for every rejected row.
            if (!validate(self, &club, true)) {
                ++not_possible;
            } else if (execute(self, &club)) {
                ++interested;
                clubs[i] |= 0x80000000u;
            } else {
                ++not_interested;
            }
        }
        refresh(self);

        std::wstring result = L"Gepr\u00fcft: " + std::to_wstring(club_count) +
            L"\nInteressiert: " + std::to_wstring(interested) +
            L"\nNicht interessiert: " + std::to_wstring(not_interested) +
            L"\nAngebot nicht m\u00f6glich: " + std::to_wstring(not_possible) + L"\n\n";
        if (interested == 0) {
            result += L"Aktuell ist keiner der sichtbaren Vereine interessiert.";
        } else {
            result += L"Diese Vereine melden sich in K\u00fcrze mit einem Angebot:\n";
            int listed = 0;
            for (int i = 0; i < club_count; ++i) {
                std::uint32_t club = clubs[i];
                // ExecuteOffer has already run. Re-evaluating it would duplicate the
                // offer, so interested IDs are recorded below during the first pass.
                if ((club & 0x80000000u) == 0) continue;
                club &= 0x7fffffffu;
                const auto found = g_club_names.find(club);
                result += L"\n- ";
                result += found != g_club_names.end()
                    ? found->second : (L"Verein #" + std::to_wstring(club));
                ++listed;
            }
            if (listed == 0) result += L"\n- Die Vereinsnamen erscheinen mit den eingehenden Angeboten.";
        }
    MessageBoxW(GetForegroundWindow(), result.c_str(), L"Spieler allen Vereinen anbieten",
        MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND);
}

void __fastcall OfferAllVisibleClubs(void* self, void*) {
    if (!self || InterlockedCompareExchange(&g_running, 1, 0) != 0) return;
    __try {
        RunOfferAll(self);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        WriteLog("HANDLER_EXCEPTION");
    }

    InterlockedExchange(&g_running, 0);
}

bool InstallHook() {
    auto* target = reinterpret_cast<unsigned char*>(g_game_base + kOfferAllHandlerRva);
    if (std::memcmp(target, kExpectedHandler, sizeof(kExpectedHandler)) != 0) return false;

    const std::intptr_t displacement =
        reinterpret_cast<std::uintptr_t>(&OfferAllVisibleClubs) -
        reinterpret_cast<std::uintptr_t>(target + 5);
    if (displacement < INT32_MIN || displacement > INT32_MAX) return false;

    unsigned char patch[5] = {0xE9};
    const std::int32_t relative = static_cast<std::int32_t>(displacement);
    std::memcpy(patch + 1, &relative, sizeof(relative));

    DWORD old_protection = 0;
    if (!VirtualProtect(target, sizeof(patch), PAGE_EXECUTE_READWRITE, &old_protection)) return false;
    std::memcpy(target, patch, sizeof(patch));
    FlushInstructionCache(GetCurrentProcess(), target, sizeof(patch));
    DWORD ignored = 0;
    VirtualProtect(target, sizeof(patch), old_protection, &ignored);
    return true;
}

DWORD WINAPI Initialize(void*) {
    g_game_base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
    LoadClubNames();
    WriteLog(g_club_names.empty() ? "CLUB_MAP_MISSING" : "CLUB_MAP_LOADED");
    for (int attempt = 0; attempt < 300; ++attempt) {
        if (InstallHook()) {
            WriteLog("PATCH_APPLIED Manager.exe SHA256 8EBE1291FBCC1291BFEE182995A165194156A0B4B8E0D6C80994CADB087A857C");
            return 0;
        }
        Sleep(100);
    }
    WriteLog("PATCH_SKIPPED_SIGNATURE_MISMATCH");
    return 1;
}

} // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    static_assert(sizeof(void*) == 4, "FM13 plugins must be built for x86");
    if (reason == DLL_PROCESS_ATTACH) {
        g_module = instance;
        DisableThreadLibraryCalls(instance);
        if (HANDLE thread = CreateThread(nullptr, 0, Initialize, nullptr, 0, nullptr)) CloseHandle(thread);
    }
    return TRUE;
}
