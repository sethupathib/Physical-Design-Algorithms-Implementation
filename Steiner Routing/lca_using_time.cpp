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
int Par[N][M], dep[N], tin[N], tout[N], timer;



void dfs(int cur, int par){
	Par[cur][0] = par;
	tin[cur]= ++timer;
	for(auto x:gr[cur]){
		if(x!=par){
			dep[x]+=dep[cur]+1;
			dfs(x,cur);
		}
	}
	tout[cur] = timer;
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
bool isAncestor(int u, int v){
	return (tin[u]<=tin[v] && tout[u]>=tout[v]);
}
int LCA_using_time(int u, int v){
	if(isAncestor(u,v)) return u;
	if(isAncestor(v,u)) return v;

	for(int i=M-1;i>=0;i--){
		//if Par[u][i] is not ancestor of v then move to it
		if(!isAncestor(Par[u][i],v)){
			u = Par[u][i];
		}
	}
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
	timer=0;
	tin[0]=0, tout[0]=n+1; //universal parent
	dfs(1,0);
	cal_sparse_table(1,0);
	cout<<lca_dp(9,15)<<endl;
	cout<<lca_dp(18,15)<<endl;
	cout<<lca_dp(15,15)<<endl;
	cout<<lca_dp(11,16)<<endl;
	cout<<"\t"<<endl;
	cout<<LCA_using_time(9,15)<<endl;
	cout<<LCA_using_time(18,15)<<endl;
	cout<<LCA_using_time(15,15)<<endl;
	cout<<LCA_using_time(11,16)<<endl;
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
