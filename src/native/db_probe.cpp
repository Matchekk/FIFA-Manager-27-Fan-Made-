// Native bridge to FIFAM. Source is always read-only; staging writes are opt-in.
// Built against a locally cloned, pinned upstream. Never linked into Manager.exe.
#include "FifamDatabase.h"
#include "FifamPlayer.h"
#include "FifamPlayerLevel.h"
#include <Windows.h>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include "stage_plan.h"

namespace fs = std::filesystem;

std::string utf8(std::wstring const& text) {
    if (text.empty()) return {};
    auto count = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text.data(),
        static_cast<int>(text.size()), nullptr, 0, nullptr, nullptr);
    if (count <= 0) throw std::runtime_error("Invalid Unicode name");
    std::string result(static_cast<size_t>(count), '\0');
    WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text.data(),
        static_cast<int>(text.size()), result.data(), count, nullptr, nullptr);
    return result;
}

std::string csv(std::wstring const& text) {
    std::string result = "\"";
    for (char c : utf8(text)) { if (c == '"') result += '"'; result += c; }
    return result + '"';
}

int wmain(int argc, wchar_t** argv) {
    try {
        const bool stagePlan = argc == 5 && std::wstring(argv[3]) == L"--stage-plan";
        const bool stageWrite = stagePlan || (argc == 4 && std::wstring(argv[3]) == L"--stage-roundtrip");
        if (argc != 3 && !stageWrite)
            throw std::runtime_error("Usage: fm27-db-probe <database-dir> <new-external-output-dir> [--stage-roundtrip | --stage-plan <csv>]");
        auto input = fs::canonical(argv[1]);
        auto output = fs::weakly_canonical(argv[2]);
        auto parent = input.parent_path().wstring();
        auto destination = output.wstring();
        std::transform(parent.begin(), parent.end(), parent.begin(), towlower);
        std::transform(destination.begin(), destination.end(), destination.begin(), towlower);
        if (destination == parent || destination.rfind(parent + L"\\", 0) == 0)
            throw std::runtime_error("Output must be outside the installation");
        if (fs::exists(output)) throw std::runtime_error("Output directory already exists");
        if (!fs::is_regular_file(input / "Countries.sav")) throw std::runtime_error("Countries.sav missing");
        // The installed product is based on FM13. Loading data does not grant
        // executable compatibility for any runtime patch.
        auto db = std::make_unique<FifamDatabase>(13, input);
        if (stagePlan) std::cout << "STAGED_SQUAD_ROWS=" << ApplyStagePlan(*db,argv[4]) << '\n';
        fs::create_directories(output);
        std::ofstream records(output / "native_players.csv", std::ios::binary);
        if (!records) throw std::runtime_error("Cannot create native projection");
        records << "fm_id,fifa_id,club_id,name,dob,main_position,style,level13,best_style,level13_best_style\n";
        std::vector<FifamPlayer*> ordered(db->mPlayers.begin(), db->mPlayers.end());
        std::sort(ordered.begin(), ordered.end(), [](auto a, auto b) { return a->mID < b->mID; });
        for (auto p : ordered) {
            auto best = FifamPlayerLevel::GetBestStyleForPlayer(p);
            records << p->mID << ',' << p->mFifaID << ',' << (p->mClub ? p->mClub->mUniqueID : 0) << ','
                << csv(p->GetName()) << ',' << p->mBirthday.ToStringA() << ','
                << csv(p->mMainPosition.ToStr()) << ',' << csv(p->mPlayingStyle.ToStr()) << ','
                << static_cast<unsigned>(FifamPlayerLevel::GetPlayerLevel13(p, p->mMainPosition, p->mPlayingStyle)) << ','
                << csv(best.ToStr()) << ','
                << static_cast<unsigned>(FifamPlayerLevel::GetPlayerLevel13(p, p->mMainPosition, best)) << '\n';
        }
        records.flush();
        if (!records) throw std::runtime_error("Native export write failed");
        std::cout << "READ_ONLY_OK players=" << db->mPlayers.size() << " clubs=" << db->mClubs.size() << '\n';
        if (stageWrite) {
            // Canonical writer only, with no transfer/rating/season edits. The
            // external output tree was checked above and must not pre-exist.
            // Generated data is for round-trip tests, never a release artifact.
            db->Write(13, FifamVersion(0x2013, 0x12), output / "database");
            std::ofstream marker(output / "STAGING_ONLY.txt");
            marker << (stagePlan ? "MODIFIED_CANDIDATE_NOT_GAME_VALIDATED\n" : "UNMODIFIED_NATIVE_REWRITE_REQUIRES_SEMANTIC_VALIDATION\n");
            marker.flush();
            if (!marker) throw std::runtime_error("Cannot write staging status");
            SYSTEMTIME captured{};
            GetSystemTime(&captured);
            std::ofstream manifest(output / "DATABASE_METADATA.txt");
            manifest << "DATABASE_SNAPSHOT_DATE=" << captured.wYear << '-';
            if (captured.wMonth < 10) manifest << '0';
            manifest << captured.wMonth << '-';
            if (captured.wDay < 10) manifest << '0';
            manifest << captured.wDay << '\n'
                << (stagePlan ? "SNAPSHOT_KIND=PARTIAL_CURRENT_SQUAD_CANDIDATE\n" : "SNAPSHOT_KIND=INSTALLED_BASELINE_CAPTURE_NOT_UPDATED_2026_27_SQUADS\n")
                << "STATUS=STAGING_ONLY_REQUIRES_FULL_VALIDATION\n";
            manifest.flush();
            if (!manifest) throw std::runtime_error("Cannot write database metadata");
            std::cout << "STAGING_WRITE_COMPLETED_NOT_VALIDATED\n";
        }
        return 0;
    } catch (std::exception const& error) {
        std::cerr << "NATIVE_PROBE_FAILED: " << error.what() << '\n';
        return 1;
    }
}
