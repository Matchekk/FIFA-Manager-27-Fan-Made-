#pragma once
#include "FifamDatabase.h"
#include "FifamPlayer.h"
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
    bool acquisitionFields=header==acquisitionSchema;
    bool expiredFields=header==expiredSchema || acquisitionFields;
    bool actions=header==actionSchema || expiredFields;
    bool typed=header==loanSchema || actions;
    if (!typed && header!=expected) throw std::runtime_error("Unexpected staging plan schema");
    if (typed) expected=acquisitionFields?acquisitionSchema:expiredFields?expiredSchema:actions?actionSchema:loanSchema;
    struct Change { FifamPlayer* player; FifamClub* target; FifamDate joined; FifamDate until; UInt number; bool reserve;
        FifamClub* owner; FifamDate loanEnd; bool freeAgent; bool resolveExpired; };
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
        if (!seen.insert(id).second || !byId.count(id)) throw std::runtime_error("Missing/repeated planned person");
        auto p=byId.at(id);
        auto old=p->mClub?p->mClub->mUniqueID:0;
        if (p->mFifaID!=PlanUInt(f[1]) || p->mBirthday!=PlanDate(f[2]) || old!=PlanUInt(f[3]))
            throw std::runtime_error("Native baseline identity/club precondition failed");
        auto action=actions?f[15]:"SQUAD";
        bool freeAgent=action=="FREE_AGENT";
        bool replaceExpired=action=="REPLACE_EXPIRED_LOAN";
        bool purchaseLoan=action=="PURCHASE_AND_LOAN";
        bool resolveExpired=action=="RESOLVE_EXPIRED_LOAN" || replaceExpired || (purchaseLoan && p->mStartingConditions.mLoan.mEnabled);
        if (action!="SQUAD" && !freeAgent && !resolveExpired && !purchaseLoan) throw std::runtime_error("Unknown native staging action");
        auto targetID=PlanUInt(f[4]);
        auto target=targetID?db.GetClubFromUID(targetID,false):nullptr;
        if (freeAgent ? (targetID!=0 || !p->mClub) : (!target || target->mIsNationalTeam))
            throw std::runtime_error("Invalid destination club/action");
        auto joined=PlanDate(f[5]), until=PlanDate(f[6]), snapshot=PlanDate(f[12]);
        if (!snapshotText.empty() && snapshotText!=f[12]) throw std::runtime_error("Mixed plan snapshot dates");
        snapshotText=f[12];
        if (joined>snapshot || (!freeAgent && until<snapshot) || joined<p->mBirthday || snapshot<FifamDate(8,9,2026))
            throw std::runtime_error("Invalid effective contract/snapshot dates");
        auto number=PlanUInt(f[7]);
        if (number>99 || (f[8]!="FIRST" && f[8]!="RESERVE")) throw std::runtime_error("Invalid team/number");
        if (freeAgent && (until.GetDays()+1!=joined.GetDays() || number!=0 || f[8]!="FIRST" || f[13]!="0" || !f[14].empty()))
            throw std::runtime_error("Invalid clubless dates/team/loan fields");
        auto& c=p->mStartingConditions;
        if (c.mRetirement.mEnabled || (c.mLoan.mEnabled && !resolveExpired) || c.mFutureTransfer.mEnabled || c.mFutureLoan.mEnabled ||
            c.mFutureJoin.mEnabled || c.mFutureReLoan.mEnabled || c.mFutureLeave.mEnabled || c.mBanUntil.mEnabled || p->mContract.mLoaned)
            throw std::runtime_error("Complex existing condition requires a typed loan/timeline plan");
        if (resolveExpired) {
            if (!expiredFields || !p->mClub || !c.mLoan.mEnabled ||
                (!replaceExpired && !purchaseLoan && (f[13]!="0" || !f[14].empty())))
                throw std::runtime_error("Expired-loan action lacks an existing loan or attempts a new loan");
            auto oldOwner=db.GetClubFromUID(PlanUInt(f[16]),false);
            auto start=PlanDate(f[17]),end=PlanDate(f[18]);
            auto option=f[19]=="-1"?-1:static_cast<long long>(PlanUInt(f[19]));
            if (!oldOwner || oldOwner->mIsNationalTeam || !c.mLoan.mLoanedClub.IsFirstTeam() ||
                c.mLoan.mLoanedClub.mPtr!=oldOwner || c.mLoan.mStartDate!=start || c.mLoan.mEndDate!=end ||
                c.mLoan.mBuyOptionValue!=option || option>2147483647ll || start<p->mBirthday || end<start || !(end<snapshot))
                throw std::runtime_error("Expired-loan native precondition mismatch");
            if (replaceExpired && (f[13]=="0" || PlanUInt(f[13])!=oldOwner->mUniqueID ||
                (joined<end && !(p->mClub==target && joined==start))))
                throw std::runtime_error("Successor loan owner or chronology differs from previous loan");
        } else if (expiredFields && (f[16]!="0" || !f[17].empty() || !f[18].empty() || f[19]!="0"))
            throw std::runtime_error("Previous-loan fields on unrelated action");
        FifamClub* owner=nullptr;
        FifamDate loanEnd;
        if (typed && f[13]!="0") {
            owner=db.GetClubFromUID(PlanUInt(f[13]),false);
            if (!owner || owner==target || owner->mIsNationalTeam)
                throw std::runtime_error("Loan owner missing or identical to borrower");
            loanEnd=PlanDate(f[14]);
            if (loanEnd<snapshot || loanEnd<joined || until<loanEnd)
                throw std::runtime_error("Loan return or owner contract dates conflict");
            if (!replaceExpired && !purchaseLoan && p->mClub!=owner && p->mClub!=target)
                throw std::runtime_error("Loan baseline club is neither owner nor borrower");
        } else if (typed && !f[14].empty()) throw std::runtime_error("Loan end without owner");
        if (purchaseLoan) {
            if (!acquisitionFields || !owner || !p->mClub || f[21].empty() || f[23].rfind("https://",0)!=0 ||
                !std::regex_match(f[24],std::regex("[0-9a-f]{64}")))
                throw std::runtime_error("Purchase-and-loan action lacks ownership/source evidence");
            auto seller=db.GetClubFromUID(PlanUInt(f[20]),false);
            auto nativeSeller=resolveExpired?c.mLoan.mLoanedClub.mPtr:p->mClub;
            if (!seller || seller->mIsNationalTeam || seller==owner || seller!=nativeSeller ||
                (resolveExpired && joined<c.mLoan.mEndDate))
                throw std::runtime_error("Purchase-and-loan seller or old loan chronology mismatch");
            if (!f[22].empty()) {
                auto purchaseDate=PlanDate(f[22]);
                if (purchaseDate<p->mBirthday || purchaseDate>joined ||
                    (resolveExpired && purchaseDate<c.mLoan.mEndDate))
                    throw std::runtime_error("Acquisition date conflicts with loan chronology");
            }
        } else if (acquisitionFields && (f[20]!="0" || !f[21].empty() || !f[22].empty() || !f[23].empty() || !f[24].empty()))
            throw std::runtime_error("Acquisition fields on unrelated action");
        changes.push_back({p,target,joined,until,number,f[8]=="RESERVE",owner,loanEnd,freeAgent,resolveExpired});
    }
    if (changes.empty()) throw std::runtime_error("Empty staging plan");
    // All rows were checked before any mutation. Only the in-memory copy changes.
    for (auto const& c:changes) {
        auto p=c.player;
        if (c.resolveExpired) p->mStartingConditions.mLoan.Disable();
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
        if (c.freeAgent) {
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
    }
    for (auto club:db.mClubs) {
        std::set<FifamPlayer*> members;
        for (auto p:club->mPlayers)
            if (p->mClub!=club || !members.insert(p).second) throw std::runtime_error("Inconsistent club membership after staging");
    }
    return {changes.size(),snapshotText};
}
