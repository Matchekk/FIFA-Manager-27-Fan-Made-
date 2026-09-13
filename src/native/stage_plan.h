#pragma once
#include "FifamDatabase.h"
#include "FifamPlayer.h"
#include <array>
#include <chrono>
#include <fstream>
#include <map>
#include <regex>
#include <set>
#include <stdexcept>

inline std::vector<std::string> PlanCsv(std::string line) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    std::vector<std::string> result;
    std::string field;
    bool quoted = false;
    for (size_t i = 0; i < line.size(); ++i) {
        if (line[i] == '"') {
            if (quoted && i + 1 < line.size() && line[i + 1] == '"') { field += '"'; ++i; }
            else quoted = !quoted;
        }
        else if (line[i] == ',' && !quoted) { result.push_back(field); field.clear(); }
        else field += line[i];
    }
    if (quoted) throw std::runtime_error("Unclosed CSV quote");
    result.push_back(field);
    return result;
}

inline UInt PlanUInt(std::string const& value) {
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
        throw std::runtime_error("Expected unsigned plan integer");
    auto parsed = std::stoull(value);
    if (parsed > 0xFFFFFFFFull) throw std::runtime_error("Plan integer overflow");
    return static_cast<UInt>(parsed);
}

inline FifamDate PlanDate(std::string const& value) {
    if (!std::regex_match(value, std::regex("[0-9]{4}-[0-9]{2}-[0-9]{2}")))
        throw std::runtime_error("Invalid plan date format");
    auto y = PlanUInt(value.substr(0,4)), m = PlanUInt(value.substr(5,2)), d = PlanUInt(value.substr(8,2));
    if (y < 1900 || y > 2100 || !std::chrono::year_month_day(std::chrono::year(static_cast<int>(y)),
        std::chrono::month(m), std::chrono::day(d)).ok()) throw std::runtime_error("Invalid calendar date");
    return FifamDate(d,m,y);
}

struct StagePlanResult { size_t rows; std::string snapshot; };

inline StagePlanResult ApplyStagePlan(FifamDatabase& db, std::filesystem::path const& path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) throw std::runtime_error("Cannot open staging plan");
    std::string line;
    std::getline(stream,line);
    if (line.rfind("\xEF\xBB\xBF",0)==0) line.erase(0,3);
    auto header=PlanCsv(line);
    std::vector<std::string> expected={"fm_id","fifa_id","dob","old_club_id","new_club_id","joined",
        "contract_until","shirt_number","team_type","status","source","source_sha256","snapshot_date"};
    auto loanSchema=expected;
    loanSchema.push_back("loan_owner_club_id");
    loanSchema.push_back("loan_end");
    auto actionSchema=loanSchema;
    actionSchema.push_back("action");
    auto expiredSchema=actionSchema;
    for (auto const* name:{"previous_loan_owner_club_id","previous_loan_start","previous_loan_end","previous_loan_buy_option"})
        expiredSchema.push_back(name);
    auto acquisitionSchema=expiredSchema;
    for (auto const* name:{"acquisition_seller_club_id","acquisition_event_key","acquisition_date","acquisition_source","acquisition_source_sha256"})
        acquisitionSchema.push_back(name);
    auto protectedSchema=acquisitionSchema;
    for (auto const* name:{"protected_condition_type","protected_condition_param0","protected_condition_param1",
        "protected_condition_param2","protected_condition_param3","protected_condition_param4"}) protectedSchema.push_back(name);
    bool protectedFields=header==protectedSchema;
    bool acquisitionFields=header==acquisitionSchema || protectedFields;
    bool expiredFields=header==expiredSchema || acquisitionFields;
    bool actions=header==actionSchema || expiredFields;
    bool typed=header==loanSchema || actions;
    if (!typed && header!=expected) throw std::runtime_error("Unexpected staging plan schema");
    if (typed) expected=protectedFields?protectedSchema:acquisitionFields?acquisitionSchema:expiredFields?expiredSchema:actions?actionSchema:loanSchema;
    struct Change { FifamPlayer* player; FifamClub* target; FifamDate joined; FifamDate until; UInt number; bool reserve;
        FifamClub* owner; FifamDate loanEnd; bool freeAgent; bool retire; bool resolveLoan; bool shirtOnly; bool movePreserve; };
    std::vector<Change> changes;
    std::map<UInt,FifamPlayer*> byId;
    for (auto p:db.mPlayers) if (!byId.emplace(p->mID,p).second) throw std::runtime_error("Duplicate native player ID");
    std::set<UInt> seen;
    std::string snapshotText;
    while (std::getline(stream,line)) {
        if (line.empty()) continue;
        auto f=PlanCsv(line);
        if (f.size()!=expected.size() || f[9]!="CONFIRMED" || f[10].rfind("https://",0)!=0 ||
            !std::regex_match(f[11],std::regex("[0-9a-f]{64}"))) throw std::runtime_error("Unconfirmed or malformed plan row");
        auto id=PlanUInt(f[0]);
        if (!seen.insert(id).second || !byId.count(id))
            throw std::runtime_error("Player "+std::to_string(id)+": missing/repeated planned person");
        auto p=byId.at(id);
        auto playerError=[&](std::string const& message) {
            throw std::runtime_error("Player "+std::to_string(id)+": "+message);
        };
        auto old=p->mClub?p->mClub->mUniqueID:0;
        if (p->mFifaID!=PlanUInt(f[1]) || p->mBirthday!=PlanDate(f[2]) || old!=PlanUInt(f[3]))
            playerError("native baseline identity/club precondition failed");
        auto action=actions?f[15]:"SQUAD";
        bool freeAgent=action=="FREE_AGENT";
        bool retire=action=="RETIRE";
        bool shirtOnly=action=="SHIRT_ONLY";
        bool preserveProtected=action=="PRESERVE_PROTECTED_SQUAD";
        bool movePreserve=action=="MOVE_PRESERVE_METADATA";
        bool clubless=freeAgent || retire;
        bool replaceExpired=action=="REPLACE_EXPIRED_LOAN";
        bool purchaseLoan=action=="PURCHASE_AND_LOAN";
        bool replaceActive=action=="REPLACE_ACTIVE_LOAN";
        bool resolveActive=action=="RESOLVE_ACTIVE_LOAN";
        bool resolveExpired=action=="RESOLVE_EXPIRED_LOAN" || replaceExpired || (purchaseLoan && p->mStartingConditions.mLoan.mEnabled);
        bool resolveLoan=resolveExpired || replaceActive || resolveActive;
        if (action!="SQUAD" && !clubless && !resolveLoan && !purchaseLoan && !shirtOnly && !preserveProtected && !movePreserve)
            playerError("unknown native staging action");
        auto targetID=PlanUInt(f[4]);
        auto target=targetID?db.GetClubFromUID(targetID,false):nullptr;
        if (clubless ? (targetID!=0 || !p->mClub) : (!target || target->mIsNationalTeam))
            playerError("invalid destination club/action");
        auto joined=PlanDate(f[5]), until=PlanDate(f[6]), snapshot=PlanDate(f[12]);
        if (!snapshotText.empty() && snapshotText!=f[12]) throw std::runtime_error("Mixed plan snapshot dates");
        snapshotText=f[12];
        if ((!movePreserve && (joined>snapshot || (!clubless && !shirtOnly && until<snapshot) || joined<p->mBirthday ||
            (!clubless && until<joined))) || snapshot<FifamDate(8,9,2026))
            playerError("invalid effective contract/snapshot dates");
        auto number=PlanUInt(f[7]);
        if (number>99 || (f[8]!="FIRST" && f[8]!="RESERVE")) playerError("invalid team/number");
        if (shirtOnly && (target!=p->mClub || joined!=p->mContract.mJoined || until!=p->mContract.mValidUntil ||
            (f[8]=="RESERVE")!=p->mInReserveTeam || f[13]!="0" || !f[14].empty() ||
            number==(p->mInReserveTeam?p->mShirtNumberReserveTeam:p->mShirtNumberFirstTeam)))
            playerError("shirt-only action differs from native club/contract/team or does not change number");
        if (movePreserve && (target==p->mClub || joined!=p->mContract.mJoined || until!=p->mContract.mValidUntil ||
            (f[8]=="RESERVE")!=p->mInReserveTeam || f[13]!="0" || !f[14].empty() ||
            number!=(p->mInReserveTeam?p->mShirtNumberReserveTeam:p->mShirtNumberFirstTeam) ||
            p->mStartingConditions.mLoan.mEnabled || p->mContract.mLoaned))
            playerError("move-preserve action changes native metadata or has an active loan");
        if (clubless && (until.GetDays()+1!=joined.GetDays() || number!=0 || f[8]!="FIRST" || f[13]!="0" || !f[14].empty()))
            playerError("invalid clubless dates/team/loan fields");
        auto& c=p->mStartingConditions;
        if (preserveProtected) {
            if (!protectedFields) playerError("protected-condition action lacks exact precondition fields");
            auto type=PlanUInt(f[25]);
            std::array<UInt,5> params{PlanUInt(f[26]),PlanUInt(f[27]),PlanUInt(f[28]),PlanUInt(f[29]),PlanUInt(f[30])};
            auto count=static_cast<UInt>(c.mInjury.mEnabled)+static_cast<UInt>(c.mLeagueBan.mEnabled)+static_cast<UInt>(c.mBanUntil.mEnabled);
            bool exact=(count==1 && !c.mRetirement.mEnabled && !c.mLoan.mEnabled && !c.mFutureTransfer.mEnabled &&
                !c.mFutureLoan.mEnabled && !c.mFutureJoin.mEnabled && !c.mFutureReLoan.mEnabled && !c.mFutureLeave.mEnabled && !p->mContract.mLoaned);
            if (type==1) exact=exact && c.mInjury.mEnabled && params[0]==c.mInjury.mStartDate.GetDays() &&
                params[1]==c.mInjury.mEndDate.GetDays() && params[2]==0 && params[3]==c.mInjury.mType.ToInt() && params[4]==0;
            else if (type==2) exact=exact && c.mLeagueBan.mEnabled && params[0]==0 && params[1]==0 && params[2]==0 &&
                params[3]==c.mLeagueBan.mNumMatches && params[4]==0;
            else if (type==7) exact=exact && c.mBanUntil.mEnabled && params[0]==0 && params[1]==c.mBanUntil.mDate.GetDays() &&
                params[2]==0 && params[3]==0 && params[4]==0;
            else exact=false;
            if (!exact) playerError("protected-condition native precondition mismatch");
        } else if (protectedFields && std::any_of(f.begin()+25,f.end(),[](auto const& value){return !value.empty();}))
            playerError("protected-condition fields on unrelated action");
        if (!shirtOnly && !preserveProtected && !movePreserve && (c.mRetirement.mEnabled || (c.mLoan.mEnabled && !resolveLoan) || c.mFutureTransfer.mEnabled || c.mFutureLoan.mEnabled ||
            c.mFutureJoin.mEnabled || c.mFutureReLoan.mEnabled || c.mFutureLeave.mEnabled || c.mBanUntil.mEnabled || p->mContract.mLoaned)
            ) playerError("complex existing condition requires a typed loan/timeline plan");
        if (resolveLoan) {
            if (!expiredFields || !p->mClub || !c.mLoan.mEnabled ||
                ((!replaceExpired && !replaceActive && !purchaseLoan) && (f[13]!="0" || !f[14].empty())))
                playerError("expired-loan action lacks an existing loan or attempts a new loan");
            auto oldOwner=db.GetClubFromUID(PlanUInt(f[16]),false);
            auto start=PlanDate(f[17]),end=PlanDate(f[18]);
            auto option=f[19]=="-1"?-1:static_cast<long long>(PlanUInt(f[19]));
            if (!oldOwner || oldOwner->mIsNationalTeam || !c.mLoan.mLoanedClub.IsFirstTeam() ||
                c.mLoan.mLoanedClub.mPtr!=oldOwner || c.mLoan.mStartDate!=start || c.mLoan.mEndDate!=end ||
                c.mLoan.mBuyOptionValue!=option || option>2147483647ll || start<p->mBirthday || end<start ||
                ((replaceActive || resolveActive) ? end<snapshot : !(end<snapshot)))
                playerError("expired-loan native precondition mismatch");
            bool evidencedEarlyBorrowerSwitch=(PlanUInt(f[13])==PlanUInt(f[16]) &&
                p->mClub!=target && joined>=start);
            if (replaceExpired && (f[13]=="0" ||
                (joined<end && !(p->mClub==target && joined==start) && !evidencedEarlyBorrowerSwitch)))
                playerError("successor loan chronology overlaps the previous loan");
            if (replaceActive && (f[13]=="0" || joined<start || joined>snapshot))
                playerError("active successor loan lacks owner or valid replacement chronology");
            if (resolveActive && (f[13]!="0" || !f[14].empty()))
                playerError("active-loan resolution attempts a successor loan");
        } else if (expiredFields && (f[16]!="0" || !f[17].empty() || !f[18].empty() || f[19]!="0"))
            playerError("previous-loan fields on unrelated action");
        FifamClub* owner=nullptr;
        FifamDate loanEnd;
        if (typed && f[13]!="0") {
            owner=db.GetClubFromUID(PlanUInt(f[13]),false);
            if (!owner || owner==target || owner->mIsNationalTeam)
                playerError("loan owner missing or identical to borrower");
            loanEnd=PlanDate(f[14]);
            if (loanEnd<snapshot || loanEnd<joined || until<loanEnd)
                playerError("loan return or owner contract dates conflict");
            if (!replaceExpired && !replaceActive && !purchaseLoan && p->mClub!=owner && p->mClub!=target)
                playerError("loan baseline club is neither owner nor borrower");
        } else if (typed && !f[14].empty()) playerError("loan end without owner");
        if (purchaseLoan) {
            if (!acquisitionFields || !owner || !p->mClub || f[21].empty() || f[23].rfind("https://",0)!=0 ||
                !std::regex_match(f[24],std::regex("[0-9a-f]{64}")))
                playerError("purchase-and-loan action lacks ownership/source evidence");
            auto seller=db.GetClubFromUID(PlanUInt(f[20]),false);
            auto nativeSeller=resolveLoan?c.mLoan.mLoanedClub.mPtr:p->mClub;
            if (!seller || seller->mIsNationalTeam || seller==owner || seller!=nativeSeller ||
                (resolveExpired && joined<c.mLoan.mEndDate))
                playerError("purchase-and-loan seller or old loan chronology mismatch");
            if (!f[22].empty()) {
                auto purchaseDate=PlanDate(f[22]);
                if (purchaseDate<p->mBirthday || purchaseDate>joined ||
                    (resolveLoan && purchaseDate<c.mLoan.mEndDate))
                    playerError("acquisition date conflicts with loan chronology");
            }
        } else if (acquisitionFields) {
            // Permanent/current-state rows may bind a reviewed event ID or
            // effective date as audit evidence. They do not author a seller,
            // acquisition source, fee, condition, or history entry.
            if (f[20]!="0" || !f[23].empty() || !f[24].empty() ||
                (!f[21].empty() && f[21].find_first_not_of("0123456789")!=std::string::npos))
                playerError("unsupported acquisition evidence on non-purchase action");
            if (!f[22].empty()) {
                auto evidenceDate=PlanDate(f[22]);
                if (evidenceDate<p->mBirthday || evidenceDate>joined)
                    playerError("acquisition evidence date conflicts with current contract");
            }
        }
        changes.push_back({p,target,joined,until,number,f[8]=="RESERVE",owner,loanEnd,freeAgent,retire,resolveLoan,shirtOnly,movePreserve});
    }
    if (changes.empty()) throw std::runtime_error("Empty staging plan");
    // All rows were checked before any mutation. Only the in-memory copy changes.
    for (auto const& c:changes) {
        auto p=c.player;
        if (c.shirtOnly) {
            if (c.reserve) p->mShirtNumberReserveTeam=static_cast<UChar>(c.number);
            else p->mShirtNumberFirstTeam=static_cast<UChar>(c.number);
            continue;
        }
        if (c.resolveLoan) p->mStartingConditions.mLoan.Disable();
        if (p->mClub!=c.target) {
            if (p->mClub) {
                auto& members=p->mClub->mPlayers;
                members.erase(std::remove(members.begin(),members.end(),p),members.end());
                for (auto& captain:p->mClub->mCaptains) if (captain==p) captain=nullptr;
            }
            if (c.target) c.target->mPlayers.push_back(p);
            p->mClub=c.target;
            p->mIsCaptain=false;
        }
        if (c.movePreserve) continue;
        if (c.freeAgent || c.retire) {
            // Without.sav contains native players with no club. Reset the ended
            // club contract; use an expired interval as the upstream converter
            // does for free agents, aligned to the evidenced release date.
            p->mContract=FifamPlayerContract{};
            p->mShirtNumberFirstTeam=0;
            p->mShirtNumberReserveTeam=0;
            // Preserve history entries and dates, but stop claiming membership.
            for (auto& entry:p->mHistory.mEntries) entry.mStillInThisClub=false;
        }
        p->mContract.mJoined=c.joined;
        p->mContract.mValidUntil=c.until;
        p->mInReserveTeam=c.reserve;
        p->mInYouthTeam=false;
        if (c.reserve) p->mShirtNumberReserveTeam=static_cast<UChar>(c.number);
        else p->mShirtNumberFirstTeam=static_cast<UChar>(c.number);
        // Canonical converter semantics: player belongs to borrower; condition 4
        // references the owning/return club. Contract.mLoaned is marked unused
        // upstream and is not invented here. No unsupported buy option is set.
        if (c.owner) p->mStartingConditions.mLoan.Setup(c.joined,c.loanEnd,FifamClubLink(c.owner),0);
        if (c.retire) p->mStartingConditions.mRetirement.Setup();
    }
    for (auto club:db.mClubs) {
        std::set<FifamPlayer*> members;
        for (auto p:club->mPlayers)
            if (p->mClub!=club || !members.insert(p).second) throw std::runtime_error("Inconsistent club membership after staging");
    }
    return {changes.size(),snapshotText};
}
