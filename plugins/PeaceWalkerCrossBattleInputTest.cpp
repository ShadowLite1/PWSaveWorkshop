// Experimental persistent neutral input fallback, NOT global exception suppression.
#include <windows.h>
#include <intrin.h>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <MinHook.h>
using Lookup = void*(__fastcall*)(unsigned char*, unsigned, unsigned, int);
static Lookup original;
static unsigned char* base;
static volatile LONG loggedMasks;
alignas(16) static unsigned char neutral[36]{};
static void Log(const char* text) {
    char path[MAX_PATH]{};
    if (!GetModuleFileNameA(nullptr,path,MAX_PATH)) return;
    char* slash=strrchr(path,'\\'); if (!slash) return;
    if (strcpy_s(slash+1,MAX_PATH-static_cast<size_t>(slash+1-path),"PeaceWalkerCrossBattleInputTest.log")) return;
    FILE* f=nullptr; if (!fopen_s(&f,path,"a")) {fprintf(f,"%s\n",text);fclose(f);}
}
// Return false on any unreadable/unrecognized map. Never suppress that failure.
static bool Find(unsigned char* map,unsigned key,unsigned char** value,bool* absent) {
    *absent=false;
    __try {
        if (!map || !map[0]) return false;
        auto* head=*reinterpret_cast<unsigned char**>(map+0x10);
        auto* node=*reinterpret_cast<unsigned char**>(head);
        for (unsigned i=0;i<4096;++i) {
            if (node==head) {*absent=true;return true;}
            if (*reinterpret_cast<unsigned*>(node+0x10)==key) {
                *value=*reinterpret_cast<unsigned char**>(node+0x18);return *value!=nullptr;
            }
            node=*reinterpret_cast<unsigned char**>(node);
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {return false;}
    return false;
}
static bool Missing(unsigned char* root,unsigned key) {
    unsigned char* nested=nullptr; bool absent=false;
    if (!Find(root,0x1512DE,&nested,&absent)||absent) return false;
    unsigned char* value=nullptr;
    return Find(nested,key,&value,&absent)&&absent;
}
static void* __fastcall Hook(unsigned char* root,unsigned table,unsigned key,int index) {
    const auto caller=reinterpret_cast<std::uintptr_t>(_ReturnAddress())-reinterpret_cast<std::uintptr_t>(base);
    const bool mask=key && key<=0x8000 && !(key&(key-1));
    if (caller>=0x3F9BB0 && caller<0x3FA310 && table==0x1512DE && index==0 && mask &&
        Missing(root,key)) {
        if (!(InterlockedOr(&loggedMasks,static_cast<LONG>(key))&static_cast<LONG>(key))) {
            char text[240]{};
            sprintf_s(text,"BYPASS: neutral input for missing key %X, caller RVA %llX. Remains enabled; controls NOT restored.",key,static_cast<unsigned long long>(caller));
            Log(text);
        }
        return neutral;
    }
    return original(root,table,key,index);
}
static DWORD WINAPI Install(void*) {
    base=reinterpret_cast<unsigned char*>(GetModuleHandleW(nullptr));
    const unsigned char sig[]={0x48,0x89,0x5c,0x24,0x08,0x48,0x89,0x74,0x24,0x10,0x57,0x48,0x83,0xec,0x30,0x49,0x63,0xd9,0x41,0x8b,0xf8};
    const unsigned char init[]={0xc7,0x87,0xa0,0,0,0,0,4,0,0};
    if (!base||memcmp(base+0x2B010,sig,sizeof(sig))||memcmp(base+0x3F995E,init,sizeof(init))) {
        Log("REFUSED: executable signatures differ; no hook installed.");return 0;
    }
    auto status=MH_Initialize();
    if(status!=MH_OK&&status!=MH_ERROR_ALREADY_INITIALIZED){Log("REFUSED: MinHook initialization failed.");return 0;}
    void* target=base+0x2B010;
    if(MH_CreateHook(target,reinterpret_cast<void*>(&Hook),reinterpret_cast<void**>(&original))!=MH_OK) {
        Log("REFUSED: cannot create hook.");return 0;
    }
    if(MH_EnableHook(target)!=MH_OK){MH_RemoveHook(target);Log("REFUSED: cannot enable hook.");return 0;}
    Log("ARMED: auto-activated persistent missing legacy input fallback only. No activation file required; no global exception handler.");return 0;
}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,void*) {
    if(reason==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(instance);HANDLE t=CreateThread(nullptr,0,Install,nullptr,0,nullptr);if(t)CloseHandle(t);}
    return TRUE;
}
