#include<iostream>
#include<vector>
using namespace std;
#define ll long long int
#define ld long double
#define F first
#define S second
#define P pair<int,int>
#define pb push_back

const int N=100005, M =22;
vector<int> gr[N];

int Par[N], dep[N];

int lca_brute(int u, int v){
	if(u==v) return u;
	//take u to be deeper than v, if not swap
	if(dep[u]<dep[v]) swap(u,v);
	//always dep[u]>dep[v];

	while(dep[u]>dep[v]){
		u = Par[u];
	}
	//they are at the same level
	while(u!=v){
		u=Par[u];
		v=Par[v];
	}
	return u;

}

void dfs(int cur, int par){
	Par[cur] = par;
	for(auto x:gr[cur]){
		if(x!=par){
			dep[x]+=dep[cur]+1;
			dfs(x,cur);
		}
	}
	return;
}

void solve()
{
	int n;
// int i,j,k,n,m,ans=0,cnt=0,sum=0;

cin>>n;
for (int i = 0; i < n-1; i++)
{
	int x,y;
	cin>>x>>y;
	gr[x].pb(y);
	gr[y].pb(x);
}
	dfs(1,0);
	// for(int i=1;i<=n;i++){
	// 	cout<<i<<" "<<dep[i]<<" "<<Par[i]<<endl;
	// }
	cout<<lca_brute(18,16)<<endl;
}

int main()
{
	// ios_base:: sync_with_stdio(false);
	// cin.tie(NULL); cout.tie(NULL);
	#ifndef ONLINE_JUDGE
	freopen("inputs.txt","r",stdin);
 	freopen("outputs.txt","w",stdout);
 	#endif
solve();
return 0;
  
}