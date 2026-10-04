#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <array>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

namespace fs = std::filesystem;
namespace {
constexpr wchar_t kGameExe[] = L"METAL GEAR SOLID PEACE WALKER.exe";

struct SignaturePatch {
    const std::uint8_t* signature;
    std::size_t signatureSize;
    std::size_t immediateOffset;
    std::uint8_t originalImmediate;
    std::uint8_t patchedImmediate;
    const char* name;
};

constexpr std::array<std::uint8_t, 22> kGetter{0x48,0x85,0xC9,0x74,0x11,0x83,0xFA,0x03,0x77,0x0C,0x48,0x63,0xC2,0x0F,0xB6,0x84,0x08,0x98,0x00,0x00,0x00,0xC3};
constexpr std::array<std::uint8_t, 13> kEffects{0x49,0xFF,0xC2,0x49,0x83,0xFA,0x04,0x0F,0x8C,0x19,0xFF,0xFF,0xFF};
constexpr std::array<std::uint8_t, 15> kSetter{0x48,0x85,0xC9,0x74,0x31,0x66,0x85,0xD2,0x78,0x2C,0x83,0xFF,0x03,0x77,0x27};
constexpr std::array<SignaturePatch, 3> kPatches{{
    {kGetter.data(), kGetter.size(), 7, 0x03, 0x07, "skill getter"},
    {kEffects.data(), kEffects.size(), 6, 0x04, 0x08, "skill effects scan"},
    {kSetter.data(), kSetter.size(), 12, 0x03, 0x07, "skill setter"},
}};

void Log(const std::string& message) {
    wchar_t modulePath[MAX_PATH]{};
    GetModuleFileNameW(nullptr, modulePath, MAX_PATH);
    std::ofstream output(fs::path(modulePath).parent_path() / L"PeaceWalkerEightSkills.log", std::ios::app);
    if (output) output << message << '\n';
}

bool SignatureMatches(const std::uint8_t* address, const SignaturePatch& patch) {
    for (std::size_t i = 0; i < patch.signatureSize; ++i) {
        if (i != patch.immediateOffset && address[i] != patch.signature[i]) return false;
    }
    const auto value = address[patch.immediateOffset];
    return value == patch.originalImmediate || value == patch.patchedImmediate;
}

std::uint8_t* FindUnique(std::uint8_t* base, std::size_t imageSize, const SignaturePatch& patch) {
    std::uint8_t* match = nullptr;
    for (std::size_t offset = 0; offset + patch.signatureSize <= imageSize; ++offset) {
        auto* candidate = base + offset;
        if (!SignatureMatches(candidate, patch)) continue;
        if (match != nullptr) return nullptr;
        match = candidate;
    }
    return match;
}

bool ApplyPatch(std::uint8_t* address, const SignaturePatch& patch, const std::uint8_t* base) {
    auto* immediate = address + patch.immediateOffset;
    std::ostringstream detail;
    detail << patch.name << " located at RVA 0x" << std::hex << (address - base) << ".";
    Log(detail.str());
    if (*immediate == patch.patchedImmediate) return true;
    DWORD oldProtect = 0;
    if (!VirtualProtect(immediate, 1, PAGE_EXECUTE_READWRITE, &oldProtect)) return false;
    *immediate = patch.patchedImmediate;
    FlushInstructionCache(GetCurrentProcess(), immediate, 1);
    DWORD ignored = 0;
    VirtualProtect(immediate, 1, oldProtect, &ignored);
    Log(std::string("Patched ") + patch.name + " from four slots to eight.");
    return true;
}

DWORD WINAPI PluginMain(void*) {
    HMODULE game = nullptr;
    while ((game = GetModuleHandleW(kGameExe)) == nullptr) Sleep(100);
    auto* base = reinterpret_cast<std::uint8_t*>(game);
    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS*>(base + dos->e_lfanew);
    const std::size_t imageSize = nt->OptionalHeader.SizeOfImage;
    std::array<std::uint8_t*, kPatches.size()> sites{};
    for (std::size_t i = 0; i < kPatches.size(); ++i) {
        sites[i] = FindUnique(base, imageSize, kPatches[i]);
        if (!sites[i]) {
            Log(std::string("Eight-skill patch not installed: could not uniquely locate ") + kPatches[i].name + ".");
            return 1;
        }
    }
    for (std::size_t i = 0; i < kPatches.size(); ++i) {
        if (!ApplyPatch(sites[i], kPatches[i], base)) {
            Log("Eight-skill patch installation failed.");
            return 2;
        }
    }
    Log("Eight-skill runtime support is active.");
    return 0;
}
}  // namespace

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        if (HANDLE thread = CreateThread(nullptr, 0, PluginMain, nullptr, 0, nullptr)) CloseHandle(thread);
    }
    return TRUE;
}
