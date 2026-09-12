#pragma once

inline void RunExpiredLoanTests(std::filesystem::path const& output) {
    const std::string header="fm_id,fifa_id,dob,old_club_id,new_club_id,joined,contract_until,shirt_number,team_type,status,source,source_sha256,snapshot_date,loan_owner_club_id,loan_end,action,previous_loan_owner_club_id,previous_loan_start,previous_loan_end,previous_loan_buy_option\n";
    for (auto const* mode:{"return","purchase","wrong-owner","wrong-start","wrong-end","wrong-option",
                          "not-expired","future","missing-loan","reserve-owner","late-invalid","unrelated-action"}) {
        const std::string name=mode;
        bool succeeds=name=="return" || name=="purchase";
        FifamDatabase db;
        auto country=db.CreateCountry(14);
        auto owner=db.CreateClub(country); owner->mUniqueID=917505; db.AddClubToMap(owner);
        auto borrower=db.CreateClub(country); borrower->mUniqueID=917506; db.AddClubToMap(borrower);
        auto p=db.CreatePlayer(borrower,1); p->mFifaID=123; p->mBirthday=FifamDate(2,1,2000);
        p->mStartingConditions.mLoan.Setup(FifamDate(1,7,2025),FifamDate(30,6,2026),FifamClubLink(owner),-1);
        p->mStartingConditions.mLeagueBan.Setup(2);
        p->mStartingConditions.mInjury.Setup(FifamDate(1,9,2026),FifamDate(10,9,2026),FifamPlayerInjuryType());
        p->mContract.mBasicSalary=12345;
        if (name=="not-expired") p->mStartingConditions.mLoan.mEndDate=FifamDate(30,6,2027);
        if (name=="missing-loan") p->mStartingConditions.mLoan.Disable();
        if (name=="reserve-owner") p->mStartingConditions.mLoan.mLoanedClub.mTeamType=FifamClubTeamType::Reserve;
        if (name=="future") p->mStartingConditions.mFutureLeave.Setup(FifamDate(1,7,2027));
        std::wstring before;
        { FifamWriter writer(&before,13,FifamVersion(0x2013,0x12)); p->Write(writer); }
        auto row="1,123,2000-01-02,917506,"+std::string(name=="purchase"?"917506":"917505")+
            ",2026-07-01,2029-06-30,7,FIRST,CONFIRMED,https://example.com/profile,"+std::string(64,'a')+
            ",2026-09-08,0,,"+(name=="unrelated-action"?"SQUAD":"RESOLVE_EXPIRED_LOAN")+","+
            (name=="wrong-owner"?"917506":"917505")+","+(name=="wrong-start"?"2025-07-02":"2025-07-01")+","+
            (name=="wrong-end"?"2026-06-29":name=="not-expired"?"2027-06-30":"2026-06-30")+","+
            (name=="wrong-option"?"0":"-1")+"\n";
        auto path=output/("expired-"+name+".csv");
        { std::ofstream file(path); file<<header<<row; if (name=="late-invalid") file<<row; }
        bool accepted=false;
        try { ApplyStagePlan(db,path); accepted=true; } catch (std::runtime_error const&) { if (succeeds) throw; }
        if (accepted!=succeeds) throw std::runtime_error("Wrong expired-loan test result: "+name);
        if (succeeds) {
            if (p->mStartingConditions.mLoan.mEnabled || p->mClub!=(name=="purchase"?borrower:owner) ||
                p->mContract.mJoined!=FifamDate(1,7,2026) || p->mContract.mValidUntil!=FifamDate(30,6,2029) ||
                p->mStartingConditions.mLeagueBan.mNumMatches!=2 || !p->mStartingConditions.mInjury.mEnabled ||
                p->mStartingConditions.mInjury.mEndDate!=FifamDate(10,9,2026) || p->mContract.mBasicSalary!=12345)
                throw std::runtime_error("Expired-loan resolution changed unrelated state: "+name);
        } else {
            std::wstring after;
            { FifamWriter writer(&after,13,FifamVersion(0x2013,0x12)); p->Write(writer); }
            if (before!=after || p->mClub!=borrower || borrower->mPlayers.size()!=1 || !owner->mPlayers.empty())
                throw std::runtime_error("Expired-loan rejection mutated player: "+name);
        }
    }
}
