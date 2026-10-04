#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <MinHook.h>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <atomic>

namespace {
uintptr_t base{};
using Count=int(__fastcall*)();
using Row=const unsigned char*(__fastcall*)(int);
Count originalCount{};Row originalRow{};
std::atomic<bool> reported{};
// Exact 12-byte rows captured in Co-op; rank is support rank, not weapon rank.
constexpr unsigned char rows[6][12]{
 {6,4,10,10,7,1,3,2,0,0,0,0},
 {5,4,8,8,7,1,3,2,0,0,0,0},
 {4,3,6,6,6,1,2,1,0,0,0,0},
 {3,3,5,4,5,1,2,1,0,0,0,0},
 {2,3,4,2,4,1,1,1,0,0,0,0},
 {1,3,3,1,3,1,1,1,0,0,0,0}};
void Log(const char* message){
 wchar_t path[MAX_PATH]{};GetModuleFileNameW(nullptr,path,MAX_PATH);
 auto slash=wcsrchr(path,L'\\');if(!slash)return;
 wcscpy_s(slash+1,MAX_PATH-(slash+1-path),L"PeaceWalkerStrikeTableTest.log");
 FILE* f{};if(!_wfopen_s(&f,path,L"a")&&f){fprintf(f,"%s\n",message);fclose(f);}
}
bool Missing(){
 // Refuse partial tables. Do not write manager fields or retain mission pointers.
 __try {
  auto context=*reinterpret_cast<uintptr_t*>(base+0x143B738);
  return context && !*reinterpret_cast<uintptr_t*>(context+0x270)
                 && !*reinterpret_cast<uintptr_t*>(context+0x278);
 } __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
int __fastcall HookCount(){
 auto result=originalCount();
 if(result==0 && Missing()){
  if(!reported.exchange(true))Log("FALLBACK used: missing support table supplied from captured Co-op rows. Effects/network still unverified.");
  return 6;
 }return result;
}
const unsigned char* __fastcall HookRow(int index){
 auto result=originalRow(index);
 if(!result && index>=0 && index<6 && Missing())return rows[index];
 return result;
}
DWORD WINAPI Install(void*){
 base=reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
 constexpr unsigned char countSig[]{0x48,0x8b,0x05,0x41,0x54,0x1e,0x01,0x48,0x85,0xc0,0x74,0x1a,0x48,0x8b,0x88,0x70,0x02,0,0};
 constexpr unsigned char rowSig[]{0x48,0x8b,0x05,0x81,0x54,0x1e,0x01,0x48,0x85,0xc0,0x74,0x2d,0x48,0x8b,0x90,0x70,0x02,0,0};
 void* ct=reinterpret_cast<void*>(base+0x2562F0);
 void* rt=reinterpret_cast<void*>(base+0x2562B0);
 if(memcmp(ct,countSig,sizeof(countSig))||memcmp(rt,rowSig,sizeof(rowSig))){Log("REFUSED: support getter signatures differ.");return 1;}
 auto status=MH_Initialize();
 if(status!=MH_OK&&status!=MH_ERROR_ALREADY_INITIALIZED){Log("REFUSED: hook initialization failed.");return 1;}
 if(MH_CreateHook(ct,reinterpret_cast<void*>(&HookCount),reinterpret_cast<void**>(&originalCount))!=MH_OK){Log("REFUSED: count hook creation failed.");return 1;}
 if(MH_CreateHook(rt,reinterpret_cast<void*>(&HookRow),reinterpret_cast<void**>(&originalRow))!=MH_OK){MH_RemoveHook(ct);Log("REFUSED: row hook creation failed.");return 1;}
 MH_QueueEnableHook(ct);MH_QueueEnableHook(rt);
 if(MH_ApplyQueued()!=MH_OK){MH_DisableHook(ct);MH_DisableHook(rt);MH_RemoveHook(ct);MH_RemoveHook(rt);Log("REFUSED: hook activation failed.");return 1;}
 Log("ACTIVE v1: captured support rows only when both native table pointers are missing. Native loaded tables, rank selection, strike actor, damage, saves, and network logic unchanged. Do not hot-unload.");return 0;
}
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID){
 if(reason==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(module);auto t=CreateThread(nullptr,0,Install,nullptr,0,nullptr);if(t)CloseHandle(t);}return TRUE;
}
