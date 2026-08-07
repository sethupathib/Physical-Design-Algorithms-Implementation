#pragma once

#include "design.hpp"

#include <string>
#include <unordered_map>
#include <vector>

namespace perc {

struct CheckResult {
  std::vector<Violation> violations;
  std::string fingerprint;
  std::string scope;
};

// In-memory metadata cache for incremental re-runs.
class MetadataStore {
 public:
  const CheckResult* get(const std::string& scope, const std::string& fp) const;
  // Last result stored for a scope (ECO fast-path when block is known untouched).
  const CheckResult* latest(const std::string& scope) const;
  void put(CheckResult result);
  int invalidate_scopes(const std::vector<std::string>& scopes);
  std::size_t size() const { return entries_.size(); }

 private:
  static std::string key(const std::string& scope, const std::string& fp);
  std::unordered_map<std::string, CheckResult> entries_;
  std::unordered_map<std::string, CheckResult> latest_;
};

}  // namespace perc
