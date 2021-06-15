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
int Par[N][M], dep[N];



void dfs(int cur, int par){
	Par[cur][0] = par;
	for(auto x:gr[cur]){
		if(x!=par){
			dep[x]+=dep[cur]+1;
			dfs(x,cur);
		}
	}
	return;
}

void cal_sparse_table(int cur, int par){
	Par[cur][0] = par;
	for(int j=1;j<M;j++){
		Par[cur][j] = Par[Par[cur][j-1]][j-1];
	}

	for(auto x: gr[cur]){
		if(x!=par){
			cal_sparse_table(x,cur);
		}
	}
}

int lca_dp(int u, int v){
	if(u==v) return u;

	if(dep[u]<dep[v]) swap(u,v);
	int diff = dep[u]- dep[v];
	// cout<<dep[u]<<" "<<dep[v]<<" "<< diff <<endl;

	for(int i=M-1;i>=0;i--){
		if((diff>>i)&1){
			u = Par[u][i];
		}
	}
	//u & v are on the same depth
	//v was ancestor of u
	if(u==v) return u;
	for(int i=M-1;i>=0;i--){
		if(Par[u][i]!=Par[v][i]){
			u = Par[u][i];
			v = Par[v][i];
		}
	}

	//I am standing on different nodes
	return Par[u][0];

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
	cal_sparse_table(1,0);
	cout<<lca_dp(18,15)<<endl;
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