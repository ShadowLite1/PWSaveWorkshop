// Reuse the verified weapon signatures and logger, not the old installer.
#define DllMain LegacyDllMainUnused
#include "PeaceWalkerVersusWeapons.cpp"
#undef DllMain

static constexpr unsigned char kItemEligibility[]={
  0x80,0x3d,0xd4,0xdf,0xfa,0x00,0x03,0x75,0x11,0x8b,0xcb,
  0xe8,0xd7,0x7e,0xfd,0xff,0x0f,0xba,0xe0,0x13,
  0x0f,0x82,0x85,0x00,0x00,0x00};
static constexpr unsigned char kItemStart[]={
  0x0f,0xb7,0x33,0x8b,0xce,0xe8,0xf6,0xce,0xa9,0xff,
  0x84,0xc0,0x74,0x16,0x80,0x3d,0xde,0x4f,0xf3,0x00,0x00,
  0x74,0x28,0x8b,0xce,0xe8,0xf2,0x4d,0xa7,0xff,0x0f,0xba,0xe0,0x13,0x73,0x1b};
static constexpr unsigned char kItemMenu[]={
  0x80,0x3d,0x58,0x9a,0xb8,0x00,0x03,0x75,0x13,0x8b,0xce,
  0xe8,0x5b,0x39,0xbb,0xff,0x0f,0xba,0xe0,0x13,
  0x0f,0x82,0xef,0x00,0x00,0x00,0xeb,0x19};
static constexpr unsigned char kJump[]={0xEB};
struct Patch {
  size_t rva; const unsigned char* expected; size_t expectedSize;
  size_t offset; const unsigned char* replacement; size_t size;
  const char* label; DWORD protection;
};
static DWORD WINAPI InstallEquipment(void*) {
  Log("v4: initializing combined Co-Op weapon/item Versus bypass.");
  auto base=reinterpret_cast<unsigned char*>(GetModuleHandleW(nullptr));
  if(!base) return 0;
  auto dos=reinterpret_cast<IMAGE_DOS_HEADER*>(base);
  if(dos->e_magic!=IMAGE_DOS_SIGNATURE) return 0;
  auto nt=reinterpret_cast<IMAGE_NT_HEADERS64*>(base+dos->e_lfanew);
  if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_AMD64) return 0;
  Patch patches[]={
    {kRva,kExpected,sizeof(kExpected),kBranch,kJump,1,"weapon eligibility",0},
    {kStartRva,kStartExpected,sizeof(kStartExpected),kStartBranch,kJump,1,"weapon Start Game",0},
    {kMenuRva,kMenuExpected,sizeof(kMenuExpected),kMenuBranch,kMenuPatch,6,"weapon menu",0},
    {0xF8D09,kItemEligibility,sizeof(kItemEligibility),7,kJump,1,"item eligibility",0},
    {0x65BDE0,kItemStart,sizeof(kItemStart),21,kJump,1,"item Start Game",0},
    {0x51D285,kItemMenu,sizeof(kItemMenu),20,kMenuPatch,6,"item menu",0}
  };
  for(auto& p:patches) {
    MEMORY_BASIC_INFORMATION mbi{};
    auto address=base+p.rva;
    if(p.rva+p.expectedSize>nt->OptionalHeader.SizeOfImage||
       !VirtualQuery(address,&mbi,sizeof(mbi))||mbi.State!=MEM_COMMIT||
       (mbi.Protect&(PAGE_NOACCESS|PAGE_GUARD))||
       address+p.expectedSize>static_cast<unsigned char*>(mbi.BaseAddress)+mbi.RegionSize||
       memcmp(address,p.expected,p.expectedSize)!=0) {
      Log("REFUSED: signature mismatch/unreadable; no patches applied.");Log(p.label);return 0;
    }
  }
  size_t protectedCount=0;
  for(auto& p:patches) {
    if(!VirtualProtect(base+p.rva+p.offset,p.size,PAGE_EXECUTE_READWRITE,&p.protection)) {
      DWORD ignored=0;
      for(size_t i=0;i<protectedCount;i++) {
        auto& old=patches[i];VirtualProtect(base+old.rva+old.offset,old.size,old.protection,&ignored);
      }
      Log("FAILED: protection change; no code bytes changed.");return 0;
    }
    protectedCount++;
  }
  for(auto& p:patches) {
    memcpy(base+p.rva+p.offset,p.replacement,p.size);
    FlushInstructionCache(GetCurrentProcess(),base+p.rva+p.offset,p.size);
  }
  for(auto& p:patches) {
    DWORD ignored=0;
    if(!VirtualProtect(base+p.rva+p.offset,p.size,p.protection,&ignored)) Log("WARNING: page protection restore failed.");
    char message[160];
    sprintf_s(message,"%s: %s at RVA %llX",memcmp(base+p.rva+p.offset,p.replacement,p.size)==0?"APPLIED":"FAILED",p.label,static_cast<unsigned long long>(p.rva+p.offset));
    Log(message);
  }
  Log("Match rules, catalog validity, quantities and item effects remain unchanged.");
  return 0;
}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID) {
  if(reason==DLL_PROCESS_ATTACH) {
    gModule=instance;DisableThreadLibraryCalls(instance);
    HANDLE thread=CreateThread(nullptr,0,InstallEquipment,nullptr,0,nullptr);
    if(thread) CloseHandle(thread);
  }
  return TRUE;
}
