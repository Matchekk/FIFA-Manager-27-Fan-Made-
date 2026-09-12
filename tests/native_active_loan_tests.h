#pragma once
#include "../src/native/stage_plan.h"

inline void RunActiveLoanTests(std::filesystem::path const& output) {
    if (std::filesystem::exists(output)) throw std::runtime_error("Active-loan test output must be new");
    std::filesystem::create_directories(output);
    const std::string header=
        "fm_id,fifa_id,dob,old_club_id,new_club_id,joined,contract_until,shirt_number,team_type,status,source,source_sha256,snapshot_date,loan_owner_club_id,loan_end,action,previous_loan_owner_club_id,previous_loan_start,previous_loan_end,previous_loan_buy_option,acquisition_seller_club_id,acquisition_event_key,acquisition_date,acquisition_source,acquisition_source_sha256\n";
    auto run=[&](std::string const& name,std::string const& action,std::string previousOwner,bool succeeds) {
        FifamDatabase db;
        auto country=db.CreateCountry(14);
        auto owner=db.CreateClub(country); owner->mUniqueID=917505; db.AddClubToMap(owner);
        auto borrower=db.CreateClub(country); borrower->mUniqueID=917506; db.AddClubToMap(borrower);
        auto target=db.CreateClub(country); target->mUniqueID=917507; db.AddClubToMap(target);
        auto p=db.CreatePlayer(borrower,1); p->mFifaID=123; p->mBirthday=FifamDate(2,1,2000);
        p->mStartingConditions.mLoan.Setup(FifamDate(1,7,2026),FifamDate(30,6,2027),FifamClubLink(owner),0);
        auto path=output/(name+".csv");
        { std::ofstream file(path); file<<header
            <<"1,123,2000-01-02,917506,917507,2026-08-01,2028-06-30,8,FIRST,CONFIRMED,https://example.com/current,"
            <<std::string(64,'a')<<",2026-09-12,"
            <<(action=="REPLACE_ACTIVE_LOAN"?"917505,2027-06-30":"0,")<<','<<action<<','
            <<previousOwner<<",2026-07-01,2027-06-30,0,0,,,,\n"; }
        bool passed=false;
        try { auto result=ApplyStagePlan(db,path); passed=result.rows==1; }
        catch (std::runtime_error const&) { if (succeeds) throw; }
        if (succeeds) {
            bool replacement=action=="REPLACE_ACTIVE_LOAN";
            if (!passed || p->mClub!=target || borrower->mPlayers.size()!=0 || target->mPlayers.size()!=1 ||
                p->mStartingConditions.mLoan.mEnabled!=replacement ||
                (replacement && (p->mStartingConditions.mLoan.mLoanedClub.mPtr!=owner ||
                                  p->mStartingConditions.mLoan.mStartDate!=FifamDate(1,8,2026) ||
                                  p->mStartingConditions.mLoan.mEndDate!=FifamDate(30,6,2027))))
                throw std::runtime_error("Active-loan result differs: "+name);
        } else if (passed || p->mClub!=borrower || borrower->mPlayers.size()!=1 || !target->mPlayers.empty() ||
                   !p->mStartingConditions.mLoan.mEnabled)
            throw std::runtime_error("Active-loan rejection mutated data: "+name);
    };
    run("replace-active","REPLACE_ACTIVE_LOAN","917505",true);
    run("resolve-active","RESOLVE_ACTIVE_LOAN","917505",true);
    run("wrong-previous-owner","REPLACE_ACTIVE_LOAN","917507",false);
    std::ofstream report(output/"NATIVE_ACTIVE_LOAN_TESTS.json");
    report<<"{\"status\":\"PASS\",\"tests\":3,\"scope\":\"guarded active-loan replacement and resolution\"}\n";
}
