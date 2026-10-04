#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstring>

// Ghidra-verified eligibility routine. Change only JNE to JMP: bypass the
// mode-specific +7C flag rejection, not the subsequent match restrictions.
static constexpr size_t kRva = 0xF8DC0;
static constexpr size_t kBranch = 0x1B;
static constexpr unsigned char kExpected[] = {
  0x40,0x53,0x48,0x83,0xec,0x20,0x8b,0xd9,0xf7,0xc1,0xff,0x03,0x00,0x00,
  0x0f,0x84,0xa0,0x00,0x00,0x00,0x80,0x3d,0x09,0xdf,0xfa,0x00,0x03,
  0x75,0x0f,0xe8,0x8e,0xa2,0xff,0xff,0x0f,0xba,0xe0,0x1c,
  0x0f,0x82,0x80,0x00,0x00,0x00};
static constexpr size_t kStartRva=0x65BD60;
static constexpr size_t kStartBranch=0x17;
static constexpr unsigned char kStartExpected[]={
  0x44,0x0f,0xb7,0x36,0x41,0x8b,0xce,0xe8,0x54,0xd0,0xa9,0xff,
  0x84,0xc0,0x74,0x17,0x40,0x38,0x3d,0x5c,0x50,0xf3,0x00,
  0x74,0x22,0x41,0x8b,0xce,0xe8,0xef,0x72,0xa9,0xff,
  0x0f,0xba,0xe0,0x1c,0x73,0x14};
static HMODULE gModule;
static constexpr size_t kMenuRva=0x521035;
static constexpr size_t kMenuBranch=0x14;
static constexpr unsigned char kMenuExpected[]={
  0x80,0x3d,0xa8,0x5c,0xb8,0x00,0x03,0x75,0x13,0x8b,0xce,
  0xe8,0x2b,0x20,0xbd,0xff,0x0f,0xba,0xe0,0x1c,
  0x0f,0x82,0x32,0x01,0x00,0x00,0xeb,0x19};
static constexpr unsigned char kMenuPatch[]={0x90,0x90,0x90,0x90,0x90,0x90};
static void Log(const char* message) {
  wchar_t path[MAX_PATH]{};
  if (!GetModuleFileNameW(gModule,path,MAX_PATH)) return;
  wchar_t* slash = wcsrchr(path,L'\\');
  if (!slash) return;
  wcscpy_s(slash+1,MAX_PATH-(slash+1-path),L"PeaceWalkerVersusWeapons.log");
  FILE* f=nullptr;
  if (_wfopen_s(&f,path,L"a") == 0 && f) {
    fprintf(f,"%s\n",message); fclose(f);
  }
}
static DWORD WINAPI Install(void*) {
  Log("v3: initializing eligibility, start-game, and menu weapon restriction bypass.");
  auto base=reinterpret_cast<unsigned char*>(GetModuleHandleW(nullptr));
  if (!base) return 0;
  auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(base);
  if (dos->e_magic != IMAGE_DOS_SIGNATURE) return 0;
  auto nt=reinterpret_cast<IMAGE_NT_HEADERS64*>(base+dos->e_lfanew);
  if (nt->Signature != IMAGE_NT_SIGNATURE ||
      nt->FileHeader.Machine != IMAGE_FILE_MACHINE_AMD64 ||
      nt->OptionalHeader.SizeOfImage < kStartRva+sizeof(kStartExpected)) {
    Log("REFUSED: incompatible executable image."); return 0;
  }
  auto target=base+kRva;
  MEMORY_BASIC_INFORMATION mbi{};
  if (!VirtualQuery(target,&mbi,sizeof(mbi)) || mbi.State != MEM_COMMIT ||
      (mbi.Protect & (PAGE_NOACCESS|PAGE_GUARD)) ||
      target+sizeof(kExpected) > static_cast<unsigned char*>(mbi.BaseAddress)+mbi.RegionSize) {
    Log("REFUSED: eligibility code is not readable."); return 0;
  }
  if (memcmp(target,kExpected,sizeof(kExpected)) != 0) {
    Log("REFUSED: code signature mismatch; no bytes changed. Check build or conflicting plugins.");
    return 0;
  }
  auto start=base+kStartRva;
  if (!VirtualQuery(start,&mbi,sizeof(mbi)) || mbi.State != MEM_COMMIT ||
      (mbi.Protect & (PAGE_NOACCESS|PAGE_GUARD)) ||
      start+sizeof(kStartExpected) > static_cast<unsigned char*>(mbi.BaseAddress)+mbi.RegionSize ||
      memcmp(start,kStartExpected,sizeof(kStartExpected)) != 0) {
    Log("REFUSED: start-game code signature mismatch/unreadable; no bytes changed."); return 0;
  }
  DWORD oldProtect=0;
  auto menu=base+kMenuRva;
  if (!VirtualQuery(menu,&mbi,sizeof(mbi)) || mbi.State != MEM_COMMIT ||
      (mbi.Protect & (PAGE_NOACCESS|PAGE_GUARD)) ||
      menu+sizeof(kMenuExpected) > static_cast<unsigned char*>(mbi.BaseAddress)+mbi.RegionSize ||
      memcmp(menu,kMenuExpected,sizeof(kMenuExpected)) != 0) {
    Log("REFUSED: menu code signature mismatch/unreadable; no bytes changed."); return 0;
  }
  if (!VirtualProtect(target+kBranch,1,PAGE_EXECUTE_READWRITE,&oldProtect)) {
    Log("FAILED: cannot change code protection; no bytes changed."); return 0;
  }
  DWORD startProtect=0, ignored=0;
  if (!VirtualProtect(start+kStartBranch,1,PAGE_EXECUTE_READWRITE,&startProtect)) {
    VirtualProtect(target+kBranch,1,oldProtect,&ignored);
    Log("FAILED: start-game protection change failed; no bytes changed."); return 0;
  }
  DWORD menuProtect=0;
  if (!VirtualProtect(menu+kMenuBranch,sizeof(kMenuPatch),PAGE_EXECUTE_READWRITE,&menuProtect)) {
    VirtualProtect(start+kStartBranch,1,startProtect,&ignored);
    VirtualProtect(target+kBranch,1,oldProtect,&ignored);
    Log("FAILED: menu protection change failed; no bytes changed."); return 0;
  }
  target[kBranch]=0xEB;
  start[kStartBranch]=0xEB;
  memcpy(menu+kMenuBranch,kMenuPatch,sizeof(kMenuPatch));
  FlushInstructionCache(GetCurrentProcess(),target+kBranch,1);
  FlushInstructionCache(GetCurrentProcess(),start+kStartBranch,1);
  FlushInstructionCache(GetCurrentProcess(),menu+kMenuBranch,sizeof(kMenuPatch));
  BOOL restored=VirtualProtect(target+kBranch,1,oldProtect,&ignored);
  BOOL startRestored=VirtualProtect(start+kStartBranch,1,startProtect,&ignored);
  BOOL menuRestored=VirtualProtect(menu+kMenuBranch,sizeof(kMenuPatch),menuProtect,&ignored);
  Log(target[kBranch]==0xEB ?
      "APPLIED: RVA F8DDB: 75 -> EB. Mode weapon rejection bypassed; match rules preserved." :
      "FAILED: patch readback mismatch.");
  Log(start[kStartBranch]==0xEB ?
      "APPLIED: RVA 65BD77: 74 -> EB. Duplicate start-game weapon rejection bypassed; item checks unchanged." :
      "FAILED: start-game patch readback mismatch.");
  Log(memcmp(menu+kMenuBranch,kMenuPatch,sizeof(kMenuPatch))==0 ?
      "APPLIED: RVA 521049: Versus menu weapon-flag exclusion bypassed; catalog checks preserved." :
      "FAILED: menu patch readback mismatch.");
  if (!restored || !startRestored || !menuRestored) Log("WARNING: original page protection could not be restored.");
  return 0;
}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID) {
  if (reason==DLL_PROCESS_ATTACH) {
    gModule=instance;
    DisableThreadLibraryCalls(instance);
    HANDLE thread=CreateThread(nullptr,0,Install,nullptr,0,nullptr);
    if (thread) CloseHandle(thread);
  }
  return TRUE;
}
