// Synthetic process for read-only counter smoke tests. No game code/assets.
#include <Windows.h>
#include <vector>
int main() {
    std::vector<unsigned char> memory(8 * 1024 * 1024, 42);
    for (int i = 0; i < 80; ++i) {
        memory[static_cast<size_t>(i) * 4096] = static_cast<unsigned char>(i);
        Sleep(100);
    }
    return memory[0];
}
