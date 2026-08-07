#include "metadata.hpp"

#include <unordered_set>

namespace perc {

std::string MetadataStore::key(const std::string& scope, const std::string& fp) {
  return scope + "::" + fp;
}

const CheckResult* MetadataStore::get(const std::string& scope, const std::string& fp) const {
  auto it = entries_.find(key(scope, fp));
  if (it == entries_.end()) return nullptr;
  return &it->second;
}

const CheckResult* MetadataStore::latest(const std::string& scope) const {
  auto it = latest_.find(scope);
  if (it == latest_.end()) return nullptr;
  return &it->second;
}

void MetadataStore::put(CheckResult result) {
  const std::string k = key(result.scope, result.fingerprint);
  latest_[result.scope] = result;
  entries_[k] = std::move(result);
}

int MetadataStore::invalidate_scopes(const std::vector<std::string>& scopes) {
  std::unordered_set<std::string> dead(scopes.begin(), scopes.end());
  int n = 0;
  for (auto it = entries_.begin(); it != entries_.end();) {
    const auto pos = it->first.find("::");
    const std::string scope = (pos == std::string::npos) ? it->first : it->first.substr(0, pos);
    if (dead.count(scope)) {
      it = entries_.erase(it);
      ++n;
    } else {
      ++it;
    }
  }
  for (const auto& s : dead) latest_.erase(s);
  return n;
}

}  // namespace perc
