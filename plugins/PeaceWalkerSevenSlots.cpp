#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <array>
#include <cstring>
#include <cstdio>

static void Log(const char* message){
    wchar_t path[MAX_PATH]{};GetModuleFileNameW(nullptr,path,MAX_PATH);
    auto slash=wcsrchr(path,L'\\');if(!slash)return;
    wcscpy_s(slash+1,MAX_PATH-(slash+1-path),L"PeaceWalkerSevenSlots.log");
    FILE* file{};if(!_wfopen_s(&file,path,L"a")&&file){fprintf(file,"%s\n",message);fclose(file);}
}
static DWORD WINAPI Install(void*){
    auto base=reinterpret_cast<unsigned char*>(GetModuleHandleW(nullptr));
    constexpr std::array<unsigned,5> coopItems{5,6,5,7,5},versusItems{2,2,2,2,2};
    constexpr std::array<unsigned,20> coopWeapons{
        2,2,4,6, 2,2,5,7, 3,3,4,7, 2,2,4,6, 1,1,4,5};
    constexpr std::array<unsigned,20> versusWeapons{
        2,2,2,4, 2,2,2,4, 2,2,2,4, 2,2,2,4, 2,2,2,4};
    // Reject conflicting eight-slot plugins as well as unsupported game versions.
    if(memcmp(base+0xF967A0,coopItems.data(),sizeof(coopItems))||
       memcmp(base+0xF967B8,versusItems.data(),sizeof(versusItems))||
       memcmp(base+0xF4C150,coopWeapons.data(),sizeof(coopWeapons))||
       memcmp(base+0xF4C1A0,versusWeapons.data(),sizeof(versusWeapons))){
        Log("REFUSED: native capacity signatures differ. Disable InventoryTest v1/v2; no tables changed.");return 1;
    }
    struct Change{size_t rva,size;DWORD protection;};
    std::array<Change,4> changes{{{0xF967A0,20,0},{0xF967B8,20,0},
        {0xF4C150,80,0},{0xF4C1A0,80,0}}};
    size_t prepared=0;
    for(auto& change:changes){
        if(!VirtualProtect(base+change.rva,change.size,PAGE_READWRITE,&change.protection)){
            for(size_t i=prepared;i>0;--i){DWORD unused;auto& old=changes[i-1];VirtualProtect(base+old.rva,old.size,old.protection,&unused);}
            Log("REFUSED: protection preparation failed; nothing changed.");return 1;
        }++prepared;
    }
    constexpr unsigned seven=7;
    for(unsigned i=0;i<5;++i){
        memcpy(base+0xF967A0+i*4,&seven,4);memcpy(base+0xF967B8+i*4,&seven,4);
        // Preserve both native primary partition columns. Increase other capacity
        // to seven minus the primary partition, and set total capacity to seven.
        const unsigned coopOther=seven-coopWeapons[i*4];
        const unsigned versusOther=seven-versusWeapons[i*4];
        memcpy(base+0xF4C150+i*16+8,&coopOther,4);
        memcpy(base+0xF4C150+i*16+12,&seven,4);
        memcpy(base+0xF4C1A0+i*16+8,&versusOther,4);
        memcpy(base+0xF4C1A0+i*16+12,&seven,4);
    }
    // Tables may share a page, so unwind protection changes in reverse order.
    for(size_t i=changes.size();i>0;--i){auto& change=changes[i-1];DWORD unused;VirtualProtect(base+change.rva,change.size,change.protection,&unused);}
    Log("ACTIVE v3: seven items and seven weapons for all five uniform categories in Campaign/Co-op and Versus. Native Empty/Stun Rod, seven-slot menus/population, and primary partitions preserved. No eighth-slot, CQC, save or network changes.");
    return 0;
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID){
    if(reason==DLL_PROCESS_ATTACH){DisableThreadLibraryCalls(module);auto thread=CreateThread(nullptr,0,Install,nullptr,0,nullptr);if(thread)CloseHandle(thread);}return TRUE;
}
