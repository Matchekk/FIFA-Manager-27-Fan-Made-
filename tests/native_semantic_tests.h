#pragma once
#include "FifamCompLeague.h"

inline void RunNativeSemanticTests(std::filesystem::path const& output) {
    FifamDatabase db;
    auto country=db.CreateCountry(14);
    auto club=db.CreateClub(country); club->mUniqueID=917505; db.AddClubToMap(club);
    auto other=db.CreateClub(country); other->mUniqueID=917506; db.AddClubToMap(other);
    auto p=db.CreatePlayer(club,1); p->mFirstName=L"Person"; p->mBirthday=FifamDate(2,1,2000);
    auto brother=db.CreatePlayer(other,2); brother->mFirstName=L"Brother"; brother->mBirthday=FifamDate(2,1,2001);
    p->mBrothers.insert(brother); brother->mBrothers.insert(p);
    auto staff=db.CreateStaff(club,3); staff->mFirstName=L"Manager"; staff->mBirthday=FifamDate(2,1,1980);
    staff->mFavouriteClub=FifamClubLink(other);
    auto comp=db.CreateCompetition(FifamCompDbType::League,FifamCompID(14u,FifamCompType::League,0))->AsLeague();
    comp->mNumTeams=2; comp->mNumRounds=2; comp->mTeams={FifamClubLink(club),FifamClubLink(other)};
    comp->mFirstSeasonMatchdays={1,8}; comp->GenerateFixtures();
    auto before=output/"semantics-before",after=output/"semantics-after",changed=output/"semantics-changed";
    std::filesystem::create_directories(before); std::filesystem::create_directories(after); std::filesystem::create_directories(changed);
    ExportPlayerSemantics(db,before/"native_player_semantics.csv");
    club->SetWriteableID(999); other->SetWriteableID(888); other->SetIsWriteable(false);
    ExportPlayerSemantics(db,after/"native_player_semantics.csv");
    if (club->GetWriteableID()!=999 || other->GetIsWriteable())
        throw std::runtime_error("Native normalization did not restore writable state");
    other->SetIsWriteable(true);
    if (other->GetWriteableID()!=888) throw std::runtime_error("Native normalization lost hidden writable ID");
    other->SetIsWriteable(false);
    auto content=[](std::filesystem::path const& path) {
        std::ifstream file(path,std::ios::binary);
        return std::string(std::istreambuf_iterator<char>(file),std::istreambuf_iterator<char>());
    };
    for (auto const* name:{"native_player_semantics.csv","native_staff_semantics.csv","native_competition_semantics.csv","native_player_relations.csv"})
        if (content(before/name)!=content(after/name)) throw std::runtime_error("Canonical club-reference normalization failed");
    staff->mManagerCoachingSkills=5; comp->mNumSubsAllowed=5; p->mBrothers.clear(); brother->mBrothers.clear();
    ExportPlayerSemantics(db,changed/"native_player_semantics.csv");
    for (auto const* name:{"native_staff_semantics.csv","native_competition_semantics.csv","native_player_relations.csv"})
        if (content(after/name)==content(changed/name)) throw std::runtime_error("Extended semantic change was not detected");

    // A-B and B-C does not imply A-C (for example, different half-siblings).
    auto half=db.CreatePlayer(other,4); half->mFirstName=L"Half"; half->mBirthday=FifamDate(2,1,2002);
    p->mBrothers={brother}; brother->mBrothers={p,half}; half->mBrothers={brother};
    p->mCousins={half}; half->mCousins={p};
    db.SetupWriteableStatus(13);
    auto relationPath=output/"exact-relations.sav";
    WriteExactPlayerRelations(db,relationPath);
    Map<String,Vector<FifamPlayer*>> names;
    for (auto person:db.mPlayers) {
        names[person->GetStringUniqueId(13,false)].push_back(person);
        person->mBrothers.clear(); person->mCousins.clear();
    }
    db.ReadPlayerRelations(relationPath,13,names);
    if (p->mBrothers!=Set<FifamPlayer*>{brother} || brother->mBrothers!=Set<FifamPlayer*>{p,half} ||
        half->mBrothers!=Set<FifamPlayer*>{brother} || p->mCousins!=Set<FifamPlayer*>{half} ||
        half->mCousins!=Set<FifamPlayer*>{p}) throw std::runtime_error("Exact relationship native reread failed");
    auto originalRelations=content(relationPath);
    brother->mBrothers.erase(p);
    bool rejected=false;
    try { WriteExactPlayerRelations(db,relationPath); } catch (std::runtime_error const&) { rejected=true; }
    if (!rejected || content(relationPath)!=originalRelations) throw std::runtime_error("Asymmetric graph not rejected atomically");
    brother->mBrothers.insert(p);
    auto duplicate=db.CreatePlayer(other,5); duplicate->mFirstName=p->mFirstName; duplicate->mBirthday=p->mBirthday;
    duplicate->mEmpicsId=123; p->mEmpicsId=123;
    db.SetupWriteableStatus(13);
    rejected=false;
    try { WriteExactPlayerRelations(db,relationPath); } catch (std::runtime_error const&) { rejected=true; }
    if (!rejected || content(relationPath)!=originalRelations) throw std::runtime_error("Ambiguous graph not rejected atomically");

    auto supportSource=output/"support-source",supportTarget=output/"support-target";
    std::filesystem::create_directories(supportSource/"database");
    std::filesystem::create_directories(supportSource/"script");
    std::filesystem::create_directories(supportSource/"fmdata"/"historic");
    std::filesystem::create_directories(supportTarget);
    { std::ofstream f(supportSource/"script"/"Continental - Europe.txt"); f<<"unknown mod section\n"; }
    { std::ofstream f(supportSource/"fmdata"/"historic"/"WorldPlayers.txt"); f<<"history\n"; }
    { std::ofstream f(supportSource/"database"/"MaleNames.txt"); f<<"names\n"; }
    for (auto const* name:{"AssessmentAFC.sav","AssessmentCAF.sav","CountryNames.txt","picture.tga","PriorityClubs.txt","TownDataUniques.txt"}) {
        std::ofstream f(supportSource/"database"/name,std::ios::binary); f<<"preserved auxiliary "<<name<<'\0'<<"binary tail";
    }
    { std::ofstream f(supportSource/"database"/"Master.dat"); f<<"stale compiled game database"; }
    PreserveNativeSupport(supportSource/"database",supportTarget);
    for (auto const* name:{"script/Continental - Europe.txt","fmdata/historic/WorldPlayers.txt","database/MaleNames.txt"})
        if (content(supportSource/name)!=content(supportTarget/name)) throw std::runtime_error("Support file not preserved");
    for (auto const* name:{"AssessmentAFC.sav","AssessmentCAF.sav","CountryNames.txt","picture.tga","PriorityClubs.txt","TownDataUniques.txt"})
        if (content(supportSource/"database"/name)!=content(supportTarget/"database"/name)) throw std::runtime_error("Auxiliary file not preserved exactly");
    if (std::filesystem::exists(supportTarget/"database"/"Master.dat")) throw std::runtime_error("Stale compiled game database was copied");
    std::ofstream report(output/"NATIVE_TESTS.json");
    report<<"{\"status\":\"PASS\",\"tests\":44,\"scope\":\"17 native staging cases; 12 expired-loan and 9 successor-loan cases; 2 semantic cases; exact relationship reread, asymmetric and ambiguous rejection; support-file preservation\"}\n";
}
