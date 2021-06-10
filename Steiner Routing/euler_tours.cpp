//Euler Tours on Trees
#include <bits/stdc++.h>
using namespace std;
const int N = 10005;
vector<int> g[N];
int tin[N],tout[N],timer=1, timer1=0;


void euler_tour_1(int current, int parent){
	cout<<current<<" ";
	tin[current] = timer++;
	for(auto x:g[current]){
		if(x!=parent){
			euler_tour_1(x,current);
			cout<<current<<" ";
			tout[current] = timer++;
		}
	}

	return;
}

void printTimerValues(int *tin,int *tout){
	cout<<endl;
	cout<<"Node "<<"T[in] "<< "T[out]"<<endl;
	for(int i=1;i<=9;i++){
		cout<<i<<" --> "<<tin[i]<<" "<<tout[i]<<endl;
	}
}

void euler_tour_2(int current, int parent){
	cout<<current<<" ";
	tin[current] = timer++;
	for(auto x:g[current]){
		if(x!=parent){
			euler_tour_2(x,current);			
		}
	}
	cout<<current<<" ";
	tout[current] = timer++;
	return;
}
void euler_tour_3(int current, int parent){
	cout<<current<<" ";
	tin[current] = ++timer1;
	for(auto x:g[current]){
		if(x!=parent){
			euler_tour_3(x,current);			
		}
	}
	tout[current] = timer1;

	// cout<<current<<" ";
	return;
}

bool isAncestor(int x, int y){
	return ((tin[x] <= tin[y] && tout[x]>= tout[y]));
}

void solve(){
	int n;
	cin>>n;
	for(int i=0;i<n-1;i++){
		int x,y;
		cin>>x>>y;
		g[x].push_back(y);
		g[y].push_back(x);
	}
	// cout<<"Euler Tour 1"<<endl;
	// euler_tour_1(1,0);
	// cout<<endl;
	// printTimerValues(tin,tout);

	// cout<<"Euler Tour 2"<<endl;
	// euler_tour_2(1,0);
	// cout<<endl;
	// printTimerValues(tin,tout);


	cout<<"Euler Tour 3"<<endl;
	euler_tour_3(1,0);
	cout<<endl;
	printTimerValues(tin,tout);
	cout<<endl<<endl;
	

	if(isAncestor(9,1))
		{
			cout<<"Node 1 is an ancestor of Node 2"<<endl; 
		}
		else cout<<" It's not an ancestor"<<endl;

}

int main(){
#ifndef ONLINE_JUDGE
	freopen("inputs.txt","r",stdin);
 	freopen("outputs.txt","w",stdout);
 	#endif


	solve();
	return 0;
}


