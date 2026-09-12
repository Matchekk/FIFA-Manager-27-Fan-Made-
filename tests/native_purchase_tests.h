#pragma once

inline void RunPurchaseLoanTests(std::filesystem::path const& output) {
    const std::string header="fm_id,fifa_id,dob,old_club_id,new_club_id,joined,contract_until,shirt_number,team_type,status,source,source_sha256,snapshot_date,loan_owner_club_id,loan_end,action,previous_loan_owner_club_id,previous_loan_start,previous_loan_end,previous_loan_buy_option,acquisition_seller_club_id,acquisition_event_key,acquisition_date,acquisition_source,acquisition_source_sha256\n";
    size_t cases=0;
    for (auto const* mode:{"purchase","expired-purchase","dated-purchase","reserve-purchase","wrong-seller",
                          "wrong-old-owner","missing-owner","same-owner","missing-proof","bad-hash",
                          "late-purchase","early-purchase","overlap","unexpired","protected","flagged",
                          "unrelated-fields","late-invalid"}) {
        ++cases;
        const std::string name=mode;
        bool succeeds=name=="purchase" || name=="expired-purchase" || name=="dated-purchase" || name=="reserve-purchase";
        bool oldLoan=name=="expired-purchase" || name=="wrong-old-owner" || name=="early-purchase" ||
            name=="overlap" || name=="unexpired";
        FifamDatabase db;
        auto country=db.CreateCountry(14);
        auto seller=db.CreateClub(country); seller->mUniqueID=917505; db.AddClubToMap(seller);
        auto owner=db.CreateClub(country); owner->mUniqueID=917506; db.AddClubToMap(owner);
        auto borrower=db.CreateClub(country); borrower->mUniqueID=917507; db.AddClubToMap(borrower);
        auto baseline=oldLoan?borrower:seller;
        auto p=db.CreatePlayer(baseline,1); p->mFifaID=123; p->mBirthday=FifamDate(2,1,2000);
        if (oldLoan) p->mStartingConditions.mLoan.Setup(FifamDate(1,7,2025),
            FifamDate(30,6,name=="unexpired"?2027:2026),FifamClubLink(seller),4000000);
        p->mStartingConditions.mLeagueBan.Setup(2); p->mContract.mBasicSalary=42;
        p->mContract.mLoaned=name=="flagged";
        if (name=="protected") p->mStartingConditions.mFutureLeave.Setup(FifamDate(1,7,2027));
        std::wstring before;
        { FifamWriter writer(&before,13,FifamVersion(0x2013,0x12)); p->Write(writer); }
        auto joined=name=="overlap"?"2025-07-01":"2026-08-01";
        auto date=name=="dated-purchase"?"2026-07-01":name=="late-purchase"?"2026-08-02":name=="early-purchase"?"2026-06-29":"";
        auto row="1,123,2000-01-02,"+std::to_string(baseline->mUniqueID)+",917507,"+joined+
            ",2029-06-30,7,"+(name=="reserve-purchase"?"RESERVE":"FIRST")+
            ",CONFIRMED,https://example.com/profile,"+std::string(64,'a')+",2026-09-08,"+
            (name=="missing-owner"?"0":(name=="same-owner" || name=="unrelated-fields")?"917505":"917506")+","+
            (name=="missing-owner"?"":"2027-06-30")+","+(name=="unrelated-fields"?"SQUAD":"PURCHASE_AND_LOAN")+","+
            (oldLoan?(name=="wrong-old-owner"?"917506,2025-07-01,2026-06-30,4000000":
                      name=="unexpired"?"917505,2025-07-01,2027-06-30,4000000":"917505,2025-07-01,2026-06-30,4000000"):"0,,,0")+","+
            (name=="wrong-seller"?"917507":"917505")+","+(name=="missing-proof"?"":"999")+","+date+
            ",https://example.com/transfers,"+(name=="bad-hash"?"bad":std::string(64,'b'))+"\n";
        auto path=output/("purchase-"+name+".csv");
        { std::ofstream file(path); file<<header<<row; if (name=="late-invalid") file<<row; }
        bool accepted=false;
        try { ApplyStagePlan(db,path); accepted=true; } catch (std::runtime_error const&) { if (succeeds) throw; }
        if (accepted!=succeeds) throw std::runtime_error("Wrong purchase-loan result: "+name);
        if (succeeds) {
            auto& loan=p->mStartingConditions.mLoan;
            if (!loan.mEnabled || loan.mLoanedClub.mPtr!=owner || loan.mStartDate!=FifamDate(1,8,2026) ||
                loan.mEndDate!=FifamDate(30,6,2027) || loan.mBuyOptionValue!=0 || p->mClub!=borrower ||
                p->mInReserveTeam!=(name=="reserve-purchase") || p->mContract.mBasicSalary!=42 ||
                p->mStartingConditions.mLeagueBan.mNumMatches!=2 || p->mContract.mLoaned ||
                borrower->mPlayers.size()!=1 || !seller->mPlayers.empty())
                throw std::runtime_error("Purchase loan invariant failed: "+name);
        } else {
            std::wstring after;
            { FifamWriter writer(&after,13,FifamVersion(0x2013,0x12)); p->Write(writer); }
            if (before!=after || p->mClub!=baseline || baseline->mPlayers.size()!=1 || !owner->mPlayers.empty() ||
                (!oldLoan && !borrower->mPlayers.empty()))
                throw std::runtime_error("Rejected purchase loan mutated baseline: "+name);
        }
    }
    std::ofstream report(output/"NATIVE_TESTS.json");
    report<<"{\"status\":\"PASS\",\"tests\":"<<(55+cases)<<",\"scope\":\"55 prior native cases plus "<<cases
          <<" purchase-and-loan cases: ownership, expired loans, chronology, provenance, protected conditions, atomic rejection\"}\n";
}
