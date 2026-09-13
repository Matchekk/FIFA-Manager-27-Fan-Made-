#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstring>

namespace {

constexpr std::uintptr_t kOfferAllHandlerRva = 0x4FC890;
constexpr std::uintptr_t kListCountRva       = 0x918600;
constexpr std::uintptr_t kListGetValueRva    = 0x9189A0;
constexpr std::uintptr_t kValidateClubRva    = 0x4FDA10;
constexpr std::uintptr_t kExecuteOfferRva    = 0x4FC8D0;
constexpr std::uintptr_t kRefreshRva         = 0x4FD3C0;
constexpr std::uintptr_t kTranslateRva       = 0x10A9B78;
constexpr std::uintptr_t kShowDialogRva      = 0x9392F0;
constexpr std::uintptr_t kTranslationMgrRva  = 0x2DE3FA8;

constexpr unsigned char kExpectedHandler[] = {
    0x56, 0x8B, 0xF1, 0x8B, 0x86, 0xB8, 0x04, 0x00,
    0x00, 0x25, 0xFF, 0xFF, 0xFF, 0x00, 0x50, 0xE8
};

using ListCountFn = int (__thiscall *)(void*);
using ListGetValueFn = std::uint32_t (__thiscall *)(void*, int, int);
using ValidateClubFn = bool (__thiscall *)(void*, std::uint32_t*, bool);
using ExecuteOfferFn = int (__thiscall *)(void*, std::uint32_t*);
using RefreshFn = void (__thiscall *)(void*);
using TranslateFn = void* (__thiscall *)(void*, const char*);
using ShowDialogFn = int (__cdecl *)(void*, void*, int, void*, int, int);

HMODULE g_module = nullptr;
std::uintptr_t g_game_base = 0;
volatile LONG g_running = 0;

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

void ShowNativeResult(void* self, int visible, int interested) {
    auto translate = reinterpret_cast<TranslateFn>(g_game_base + kTranslateRva);
    auto show_dialog = reinterpret_cast<ShowDialogFn>(g_game_base + kShowDialogRva);
    void* translations = reinterpret_cast<void*>(g_game_base + kTranslationMgrRva);
    const char* title_key = nullptr;
    const char* body_key = nullptr;
    if (visible == 0) {
        title_key = "IDS_TRANSFER_OTHER_CLUBS";
        body_key = "IDS_PI_NOINTERESTEDCLUBS";
    } else if (interested > 0) {
        title_key = "IDS_TRANSFER_BUYING";
        body_key = "IDS_OTC_INTRESTED";
    } else {
        title_key = "IDS_TRANSFERTOPPLAYER_REJECTION";
        body_key = "IDS_OTC_NOT_INTRESTED";
    }
    void* title = translate(translations, title_key);
    void* body = translate(translations, body_key);
    show_dialog(body, title, 0, self, 0, 0);
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
    for (int i = 0; i < club_count; ++i) {
        std::uint32_t club = clubs[i];
        // Silent validation uses the game's normal eligibility checks without
        // opening one modal dialog for every rejected row.
        if (validate(self, &club, true) && execute(self, &club)) ++interested;
    }
    refresh(self);
    ShowNativeResult(self, club_count, interested);
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
