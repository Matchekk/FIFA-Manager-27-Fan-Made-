#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstring>

namespace {

constexpr std::uintptr_t kKnowledgeGetterRva = 0xAB9BA0;
constexpr unsigned char kExpectedGetter[] = {
    0x83, 0xEC, 0x0C, 0x55, 0x57, 0x8B, 0xF9, 0xF6,
    0x47, 0x64, 0x01, 0x0F, 0x84, 0xB9, 0x00, 0x00
};
constexpr unsigned char kReturnMaximumKnowledge[] = {
    0xB8, 0x0A, 0x00, 0x00, 0x00, // mov eax, 10
    0xC2, 0x04, 0x00              // ret 4
};

HMODULE g_module = nullptr;

void WriteLog(const char* message) {
    char module_path[MAX_PATH]{};
    if (!GetModuleFileNameA(g_module, module_path, MAX_PATH)) return;
    char* slash = std::strrchr(module_path, '\\');
    if (!slash) return;
    strcpy_s(slash + 1, MAX_PATH - static_cast<size_t>(slash + 1 - module_path),
        "FM27.FullPlayerKnowledge.log");
    FILE* file = nullptr;
    if (fopen_s(&file, module_path, "a") == 0 && file) {
        SYSTEMTIME now{};
        GetLocalTime(&now);
        std::fprintf(file, "%04u-%02u-%02u %02u:%02u:%02u %s\n",
            now.wYear, now.wMonth, now.wDay, now.wHour,
            now.wMinute, now.wSecond, message);
        std::fclose(file);
    }
}

bool InstallPatch() {
    const auto game_base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
    auto* target = reinterpret_cast<unsigned char*>(game_base + kKnowledgeGetterRva);
    if (std::memcmp(target, kExpectedGetter, sizeof(kExpectedGetter)) != 0) return false;

    DWORD old_protection = 0;
    if (!VirtualProtect(target, sizeof(kReturnMaximumKnowledge),
            PAGE_EXECUTE_READWRITE, &old_protection)) return false;
    std::memcpy(target, kReturnMaximumKnowledge, sizeof(kReturnMaximumKnowledge));
    FlushInstructionCache(GetCurrentProcess(), target, sizeof(kReturnMaximumKnowledge));
    DWORD ignored = 0;
    VirtualProtect(target, sizeof(kReturnMaximumKnowledge), old_protection, &ignored);
    return true;
}

DWORD WINAPI Initialize(void*) {
    for (int attempt = 0; attempt < 300; ++attempt) {
        if (InstallPatch()) {
            WriteLog("PATCH_APPLIED knowledge=10 Manager.exe SHA256 8EBE1291FBCC1291BFEE182995A165194156A0B4B8E0D6C80994CADB087A857C");
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
        if (HANDLE thread = CreateThread(nullptr, 0, Initialize, nullptr, 0, nullptr)) {
            CloseHandle(thread);
        }
    }
    return TRUE;
}
