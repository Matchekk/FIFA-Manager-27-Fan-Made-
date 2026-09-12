#pragma once

inline void RunSuccessorLoanTests(std::filesystem::path const& output) {
    const std::string header="fm_id,fifa_id,dob,old_club_id,new_club_id,joined,contract_until,shirt_number,team_type,status,source,source_sha256,snapshot_date,loan_owner_club_id,loan_end,action,previous_loan_owner_club_id,previous_loan_start,previous_loan_end,previous_loan_buy_option\n";
    for (auto const* mode:{"successor","changed-owner","extension","reserve-borrower","early-switch",
                          "early-changed-owner","early-missing-date","early-unexpired","wrong-new-owner","overlap",
                          "old-owner-change","missing-new-end","future-protected","late-invalid"}) {
        const std::string name=mode;
        bool succeeds=name=="successor" || name=="changed-owner" || name=="extension" || name=="reserve-borrower" ||
            name=="early-switch";
        FifamDatabase db;
        auto country=db.CreateCountry(14);
        auto owner=db.CreateClub(country); owner->mUniqueID=917505; db.AddClubToMap(owner);
        auto previous=db.CreateClub(country); previous->mUniqueID=917506; db.AddClubToMap(previous);
        auto next=db.CreateClub(country); next->mUniqueID=917507; db.AddClubToMap(next);
        auto newOwner=db.CreateClub(country); newOwner->mUniqueID=917508; db.AddClubToMap(newOwner);
        auto p=db.CreatePlayer(previous,1); p->mFifaID=123; p->mBirthday=FifamDate(2,1,2000);
        p->mStartingConditions.mLoan.Setup(FifamDate(1,7,2025),
            name=="early-unexpired"?FifamDate(30,6,2027):FifamDate(30,6,2026),FifamClubLink(owner),-1);
        p->mStartingConditions.mLeagueBan.Setup(2); p->mContract.mBasicSalary=42;
        if (name=="future-protected") p->mStartingConditions.mFutureLeave.Setup(FifamDate(1,7,2027));
        std::wstring before;
        { FifamWriter writer(&before,13,FifamVersion(0x2013,0x12)); p->Write(writer); }
        auto joined=name=="early-missing-date"?"":
            name=="extension"?"2025-07-01":name=="overlap"?"2025-06-01":
            name.rfind("early-",0)==0 || name=="early-switch"?"2026-01-15":"2026-08-01";
        auto row="1,123,2000-01-02,917506,"+std::string(name=="extension"?"917506":"917507")+","+joined+
            ",2029-06-30,7,"+(name=="reserve-borrower"?"RESERVE":"FIRST")+
            ",CONFIRMED,https://example.com/profile,"+std::string(64,'a')+",2026-09-08,"+
            (name=="wrong-new-owner"?"917507":(name=="changed-owner" || name=="early-changed-owner")?"917508":"917505")+","+(name=="missing-new-end"?"":"2027-06-30")+
            ",REPLACE_EXPIRED_LOAN,"+(name=="old-owner-change"?"917507":"917505")+",2025-07-01,2026-06-30,-1\n";
        if (name=="early-unexpired") {
            auto marker=std::string(",2025-07-01,2026-06-30,-1\n");
            row.replace(row.rfind(marker),marker.size(),",2025-07-01,2027-06-30,-1\n");
        }
        auto path=output/("successor-"+name+".csv");
        { std::ofstream file(path); file<<header<<row; if (name=="late-invalid") file<<row; }
        bool accepted=false;
        try { ApplyStagePlan(db,path); accepted=true; } catch (std::runtime_error const&) { if (succeeds) throw; }
        if (accepted!=succeeds) throw std::runtime_error("Wrong successor test result: "+name);
        if (succeeds) {
            auto& loan=p->mStartingConditions.mLoan;
            if (!loan.mEnabled || loan.mLoanedClub.mPtr!=(name=="changed-owner"?newOwner:owner) || loan.mStartDate!=PlanDate(joined) ||
                loan.mEndDate!=FifamDate(30,6,2027) || loan.mBuyOptionValue!=0 ||
                p->mClub!=(name=="extension"?previous:next) || p->mInReserveTeam!=(name=="reserve-borrower") ||
                p->mContract.mBasicSalary!=42 || p->mStartingConditions.mLeagueBan.mNumMatches!=2 || p->mContract.mLoaned)
                throw std::runtime_error("Native successor invariants failed: "+name);
        } else {
            std::wstring after;
            { FifamWriter writer(&after,13,FifamVersion(0x2013,0x12)); p->Write(writer); }
            if (before!=after || p->mClub!=previous || previous->mPlayers.size()!=1 || !next->mPlayers.empty())
                throw std::runtime_error("Rejected successor mutated baseline: "+name);
        }
    }
}
