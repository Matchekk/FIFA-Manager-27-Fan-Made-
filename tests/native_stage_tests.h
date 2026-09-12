#pragma once
#include "../src/native/stage_plan.h"

inline void RunStagePlanTests(std::filesystem::path const& output) {
    if (std::filesystem::exists(output)) throw std::runtime_error("Test output must be new");
    std::filesystem::create_directories(output);
    const std::string header="fm_id,fifa_id,dob,old_club_id,new_club_id,joined,contract_until,shirt_number,team_type,status,source,source_sha256,snapshot_date,loan_owner_club_id,loan_end\n";
    const std::string prefix="1,123,2000-01-02,917505,917506,2026-08-01,2029-06-30,7,FIRST,CONFIRMED,https://example.com/profile,";
    auto makeRow=[&](std::string const& snapshot,std::string const& owner,std::string const& end) {
        return prefix+std::string(64,'a')+","+snapshot+","+owner+","+end+"\n";
    };
    auto test=[&](std::string const& name,std::string const& rows,bool future,bool succeeds,bool isLoan,bool startsFree=false) {
        FifamDatabase db;
        auto country=db.CreateCountry(14);
        auto owner=db.CreateClub(country); owner->mUniqueID=917505; db.AddClubToMap(owner);
        auto borrower=db.CreateClub(country); borrower->mUniqueID=917506; db.AddClubToMap(borrower);
        auto p=db.CreatePlayer(startsFree?nullptr:owner,1);
        p->mFifaID=123; p->mBirthday=FifamDate(2,1,2000);
        p->mIsCaptain=!startsFree; owner->mCaptains[0]=startsFree?nullptr:p;
        p->mStartingConditions.mLeagueBan.Setup(2);
        if (future) p->mStartingConditions.mFutureTransfer.Setup(FifamDate(1,7,2027),FifamDate(30,6,2030),FifamClubLink(borrower),0);
        auto path=output/(name+".csv");
        { std::ofstream file(path); file<<header<<rows; }
        bool passed=false;
        try { auto result=ApplyStagePlan(db,path); passed=result.rows==1 && result.snapshot=="2026-09-08"; }
        catch (std::runtime_error const&) { if (succeeds) throw; }
        if (succeeds) {
            if (!passed || p->mClub!=borrower || !owner->mPlayers.empty() || borrower->mPlayers.size()!=1 ||
                owner->mCaptains[0] || p->mIsCaptain || p->mStartingConditions.mLeagueBan.mNumMatches!=2 ||
                p->mStartingConditions.mLoan.mEnabled!=isLoan)
                throw std::runtime_error("Native success invariants failed: "+name);
            if (isLoan && (p->mStartingConditions.mLoan.mLoanedClub.mPtr!=owner ||
                p->mStartingConditions.mLoan.mEndDate!=FifamDate(31,5,2027) || p->mContract.mLoaned))
                throw std::runtime_error("Native loan ownership/return failed: "+name);
        } else if (passed || p->mClub!=owner || owner->mPlayers.size()!=1 || !borrower->mPlayers.empty() ||
                    owner->mCaptains[0]!=p || p->mStartingConditions.mLoan.mEnabled ||
                    p->mStartingConditions.mFutureTransfer.mEnabled!=future)
            throw std::runtime_error("Native fail-before-mutation failed: "+name);
    };
    test("permanent",makeRow("2026-09-08","0",""),false,true,false);
    test("loan",makeRow("2026-09-08","917505","2027-05-31"),false,true,true);
    test("future-protected",makeRow("2026-09-08","917505","2027-05-31"),true,false,false);
    test("missing-owner",makeRow("2026-09-08","999999","2027-05-31"),false,false,false);
    test("owner-equals-borrower",makeRow("2026-09-08","917506","2027-05-31"),false,false,false);
    test("expired-return",makeRow("2026-09-08","917505","2026-08-31"),false,false,false);
    test("return-after-contract",makeRow("2026-09-08","917505","2030-05-31"),false,false,false);
    test("return-without-owner",makeRow("2026-09-08","0","2027-05-31"),false,false,false);
    auto second=makeRow("2026-09-09","0",""); second.replace(0,1,"2");
    test("late-invalid-row",makeRow("2026-09-08","0","")+second,false,false,false);
    auto freeSigning=makeRow("2026-09-08","0","");
    freeSigning.replace(freeSigning.find(",917505,"),8,",0,");
    test("sign-native-free-agent",freeSigning,false,true,false,true);
    auto releaseTest=[&](std::string const& name,std::string const& target,std::string const& until,
                         std::string const& action,bool future,bool succeeds,bool actionColumn=true,bool retires=false) {
        FifamDatabase db;
        auto country=db.CreateCountry(14);
        auto club=db.CreateClub(country); club->mUniqueID=917505; db.AddClubToMap(club);
        auto p=db.CreatePlayer(club,1);
        p->mFifaID=123; p->mBirthday=FifamDate(2,1,2000);
        p->mIsCaptain=true; club->mCaptains[0]=p;
        p->mInReserveTeam=true; p->mShirtNumberReserveTeam=9;
        p->mContract.mBasicSalary=100000; p->mContract.mOptionClub=2;
        p->mStartingConditions.mLeagueBan.Setup(2);
        if (future) p->mStartingConditions.mFutureLeave.Setup(FifamDate(1,7,2027));
        FifamPlayerHistoryEntry entry;
        entry.mClub=FifamClubLink(club); entry.mStillInThisClub=true; entry.mMatches=25;
        p->mHistory.mEntries.push_back(entry);
        auto path=output/(name+".csv");
        { std::ofstream file(path);
          file<<header.substr(0,header.size()-1)<<(actionColumn?",action\n":"\n")
              <<"1,123,2000-01-02,917505,"<<target<<",2026-07-01,"<<until
              <<",0,FIRST,CONFIRMED,https://example.com/profile,"<<std::string(64,'a')<<",2026-09-08,0,"
              <<(actionColumn?","+action:"")<<'\n'; }
        bool passed=false;
        try { ApplyStagePlan(db,path); passed=true; }
        catch (std::runtime_error const&) { if (succeeds) throw; }
        if (succeeds) {
            if (!passed || p->mClub || !club->mPlayers.empty() || club->mCaptains[0] || p->mIsCaptain ||
                p->mInReserveTeam || p->mShirtNumberReserveTeam || p->mContract.mBasicSalary || p->mContract.mOptionClub ||
                p->mContract.mJoined!=FifamDate(1,7,2026) || p->mContract.mValidUntil!=FifamDate(30,6,2026) ||
                p->mHistory.mEntries[0].mStillInThisClub || p->mHistory.mEntries[0].mMatches!=25 ||
                p->mStartingConditions.mLeagueBan.mNumMatches!=2 || p->mStartingConditions.mRetirement.mEnabled!=retires ||
                db.mPlayers.size()!=1)
                throw std::runtime_error("Native release invariants failed: "+name);
        } else if (passed || p->mClub!=club || club->mPlayers.size()!=1 || club->mCaptains[0]!=p ||
                   p->mContract.mBasicSalary!=100000 || !p->mHistory.mEntries[0].mStillInThisClub)
            throw std::runtime_error("Native release failure mutated data: "+name);
    };
    releaseTest("free-agent","0","2026-06-30","FREE_AGENT",false,true);
    releaseTest("free-agent-future-protected","0","2026-06-30","FREE_AGENT",true,false);
    releaseTest("free-agent-current-contract","0","2027-06-30","FREE_AGENT",false,false);
    releaseTest("free-agent-wrong-expiry","0","2026-06-29","FREE_AGENT",false,false);
    releaseTest("free-agent-club-target","917505","2026-06-30","FREE_AGENT",false,false);
    releaseTest("retire","0","2026-06-30","RETIRE",false,true,true,true);
    releaseTest("unknown-action","0","2026-06-30","RETIRED",false,false);
    releaseTest("zero-club-untyped","0","2026-06-30","",false,false,false);
    auto shirtOnlyTest=[&](std::string const& name,std::string const& target,bool succeeds) {
        FifamDatabase db;
        auto country=db.CreateCountry(14);
        auto club=db.CreateClub(country); club->mUniqueID=917505; db.AddClubToMap(club);
        auto other=db.CreateClub(country); other->mUniqueID=917506; db.AddClubToMap(other);
        auto p=db.CreatePlayer(club,1); p->mFifaID=123; p->mBirthday=FifamDate(2,1,2000);
        p->mContract.mJoined=FifamDate(1,7,2024); p->mContract.mValidUntil=FifamDate(30,6,2026);
        p->mShirtNumberFirstTeam=4; p->mStartingConditions.mFutureLeave.Setup(FifamDate(1,7,2027));
        auto path=output/(name+".csv");
        { std::ofstream file(path); file<<header.substr(0,header.size()-1)<<",action\n"
            <<"1,123,2000-01-02,917505,"<<target
            <<",2024-07-01,2026-06-30,2,FIRST,CONFIRMED,https://example.com/profile,"
            <<std::string(64,'a')<<",2026-09-08,0,,SHIRT_ONLY\n"; }
        bool passed=false;
        try { ApplyStagePlan(db,path); passed=true; } catch (std::runtime_error const&) { if (succeeds) throw; }
        if (succeeds) {
            if (!passed || p->mClub!=club || p->mShirtNumberFirstTeam!=2 ||
                p->mContract.mJoined!=FifamDate(1,7,2024) || p->mContract.mValidUntil!=FifamDate(30,6,2026) ||
                !p->mStartingConditions.mFutureLeave.mEnabled)
                throw std::runtime_error("Shirt-only preservation failed: "+name);
        } else if (passed || p->mClub!=club || p->mShirtNumberFirstTeam!=4 ||
                   !p->mStartingConditions.mFutureLeave.mEnabled)
            throw std::runtime_error("Shirt-only rejection mutated data: "+name);
    };
    shirtOnlyTest("shirt-only-preserves-expired-contract-and-future","917505",true);
    shirtOnlyTest("shirt-only-wrong-club","917506",false);
    {
        FifamDatabase db; auto country=db.CreateCountry(14);
        auto oldClub=db.CreateClub(country); oldClub->mUniqueID=917505; db.AddClubToMap(oldClub);
        auto newClub=db.CreateClub(country); newClub->mUniqueID=917506; db.AddClubToMap(newClub);
        auto p=db.CreatePlayer(oldClub,1); p->mFifaID=123; p->mBirthday=FifamDate(2,1,2000);
        auto path=output/"permanent-event-audit-fields.csv";
        { std::ofstream file(path);
          file<<"fm_id,fifa_id,dob,old_club_id,new_club_id,joined,contract_until,shirt_number,team_type,status,source,source_sha256,snapshot_date,loan_owner_club_id,loan_end,action,previous_loan_owner_club_id,previous_loan_start,previous_loan_end,previous_loan_buy_option,acquisition_seller_club_id,acquisition_event_key,acquisition_date,acquisition_source,acquisition_source_sha256\n"
              <<"1,123,2000-01-02,917505,917506,2026-08-01,2029-06-30,7,FIRST,CONFIRMED,https://example.com/profile,"
              <<std::string(64,'a')<<",2026-09-08,0,,SQUAD,0,,,0,0,6575989,2026-08-01,,\n"; }
        ApplyStagePlan(db,path);
        if (p->mClub!=newClub || p->mContract.mJoined!=FifamDate(1,8,2026))
            throw std::runtime_error("Permanent event audit fields changed staging semantics");
    }
    auto protectedTest=[&](std::string const& name,UInt matches,bool future,bool succeeds) {
        FifamDatabase db; auto country=db.CreateCountry(14);
        auto oldClub=db.CreateClub(country); oldClub->mUniqueID=917505; db.AddClubToMap(oldClub);
        auto newClub=db.CreateClub(country); newClub->mUniqueID=917506; db.AddClubToMap(newClub);
        auto p=db.CreatePlayer(oldClub,1); p->mFifaID=123; p->mBirthday=FifamDate(2,1,2000);
        p->mStartingConditions.mLeagueBan.Setup(2);
        if (future) p->mStartingConditions.mFutureLeave.Setup(FifamDate(1,7,2027));
        auto path=output/(name+".csv");
        { std::ofstream file(path);
          file<<"fm_id,fifa_id,dob,old_club_id,new_club_id,joined,contract_until,shirt_number,team_type,status,source,source_sha256,snapshot_date,loan_owner_club_id,loan_end,action,previous_loan_owner_club_id,previous_loan_start,previous_loan_end,previous_loan_buy_option,acquisition_seller_club_id,acquisition_event_key,acquisition_date,acquisition_source,acquisition_source_sha256,protected_condition_type,protected_condition_param0,protected_condition_param1,protected_condition_param2,protected_condition_param3,protected_condition_param4\n"
              <<"1,123,2000-01-02,917505,917506,2026-08-01,2029-06-30,7,FIRST,CONFIRMED,https://example.com/profile,"
              <<std::string(64,'a')<<",2026-09-08,0,,PRESERVE_PROTECTED_SQUAD,0,,,0,0,,,,,2,0,0,0,"
              <<matches<<",0\n"; }
        bool passed=false; try { ApplyStagePlan(db,path); passed=true; }
        catch (std::runtime_error const&) { if (succeeds) throw; }
        if (succeeds) {
            if (!passed || p->mClub!=newClub || !p->mStartingConditions.mLeagueBan.mEnabled ||
                p->mStartingConditions.mLeagueBan.mNumMatches!=2)
                throw std::runtime_error("Protected-condition preservation failed: "+name);
        } else if (passed || p->mClub!=oldClub || p->mStartingConditions.mLeagueBan.mNumMatches!=2)
            throw std::runtime_error("Protected-condition rejection mutated data: "+name);
    };
    protectedTest("protected-league-ban",2,false,true);
    protectedTest("protected-wrong-param",1,false,false);
    protectedTest("protected-future-conflict",2,true,false);
    std::ofstream protectedReport(output/"PROTECTED_CONDITION_TESTS.json");
    protectedReport<<"{\"status\":\"PASS\",\"tests\":3,\"scope\":\"exact league-ban preservation, mismatched parameter rejection and unrelated future-condition rejection\"}\n";
    std::ofstream report(output/"NATIVE_TESTS.json");
    report<<"{\"status\":\"PASS\",\"tests\":24,\"scope\":\"native staging preconditions, ownership, return, release, retirement, guarded shirt-only edits, exact protected-condition preservation, audit event fields and free-agent signing, protected future conditions, atomic validation\"}\n";
}
