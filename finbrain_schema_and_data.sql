--
-- PostgreSQL database dump
--

-- Dumped from database version 16.9
-- Dumped by pg_dump version 17.5

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: expenses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.expenses (
    id integer NOT NULL,
    user_id character varying(255) NOT NULL,
    description text,
    amount numeric(10,2) NOT NULL,
    category character varying(50) NOT NULL,
    currency character varying(10),
    date date NOT NULL,
    "time" time without time zone NOT NULL,
    month character varying(7) NOT NULL,
    unique_id text NOT NULL,
    created_at timestamp without time zone,
    platform character varying(20),
    original_message text,
    ai_insights text
);


--
-- Name: expenses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.expenses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: expenses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.expenses_id_seq OWNED BY public.expenses.id;


--
-- Name: monthly_summaries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.monthly_summaries (
    id integer NOT NULL,
    user_id_hash character varying(255) NOT NULL,
    month character varying(7) NOT NULL,
    total_amount numeric(12,2) NOT NULL,
    expense_count integer NOT NULL,
    categories json,
    ai_insights text,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: monthly_summaries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.monthly_summaries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: monthly_summaries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.monthly_summaries_id_seq OWNED BY public.monthly_summaries.id;


--
-- Name: rate_limits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rate_limits (
    id integer NOT NULL,
    user_id_hash character varying(255) NOT NULL,
    platform character varying(20) NOT NULL,
    daily_count integer,
    hourly_count integer,
    last_daily_reset date,
    last_hourly_reset timestamp without time zone,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: rate_limits_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.rate_limits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: rate_limits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.rate_limits_id_seq OWNED BY public.rate_limits.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    user_id_hash character varying(255) NOT NULL,
    platform character varying(20) NOT NULL,
    total_expenses numeric(12,2),
    expense_count integer,
    created_at timestamp without time zone,
    last_interaction timestamp without time zone,
    last_user_message_at timestamp without time zone,
    daily_message_count integer,
    hourly_message_count integer,
    last_daily_reset date,
    last_hourly_reset timestamp without time zone,
    is_new boolean,
    has_completed_onboarding boolean,
    onboarding_step integer,
    interaction_count integer,
    first_name character varying(100),
    income_range character varying(50),
    spending_categories json,
    primary_category character varying(50),
    focus_area character varying(50),
    additional_info json,
    preferences json
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: expenses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expenses ALTER COLUMN id SET DEFAULT nextval('public.expenses_id_seq'::regclass);


--
-- Name: monthly_summaries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.monthly_summaries ALTER COLUMN id SET DEFAULT nextval('public.monthly_summaries_id_seq'::regclass);


--
-- Name: rate_limits id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rate_limits ALTER COLUMN id SET DEFAULT nextval('public.rate_limits_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: expenses; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.expenses (id, user_id, description, amount, category, currency, date, "time", month, unique_id, created_at, platform, original_message, ai_insights) FROM stdin;
1	9406d3902955fd67c5bb9bdaa24bb580cf38f5821d8e6b7678ff6950156ba0ec	coffee	100.00	food	৳	2025-08-17	12:36:35.516082	2025-08	production_test_user-100.0-coffee	2025-08-17 12:36:35.517822	messenger	coffee 100, burger 300 and watermelon juice 300	
2	9406d3902955fd67c5bb9bdaa24bb580cf38f5821d8e6b7678ff6950156ba0ec	burger	300.00	food	৳	2025-08-17	12:36:38.696133	2025-08	production_test_user-300.0-burger	2025-08-17 12:36:38.696909	messenger	coffee 100, burger 300 and watermelon juice 300	
3	9406d3902955fd67c5bb9bdaa24bb580cf38f5821d8e6b7678ff6950156ba0ec	watermelon juice	300.00	food	৳	2025-08-17	12:36:40.725371	2025-08	production_test_user-300.0-watermelon	2025-08-17 12:36:40.726071	messenger	coffee 100, burger 300 and watermelon juice 300	
4	fe9853b6f04f5ebcff7f52edab15c11b2f1cde64fa3544c7afdff6fc16ccffc5	coffee	100.00	other	৳	2025-08-17	12:36:46.143338	2025-08	simple_production_test-100.0-coffee	2025-08-17 12:36:46.14389	messenger	coffee 100	
5	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	Coffee	100.00	other	৳	2025-08-17	12:40:15.934502	2025-08	30522114904098519-100.0-Coffee	2025-08-17 12:40:15.938004	messenger	Coffee 100	
6	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	Uber ride	500.00	other	৳	2025-08-17	12:40:26.49787	2025-08	30522114904098519-500.0-Uber ride	2025-08-17 12:40:26.499262	messenger	Uber ride 500	
7	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	bought clothes for	1000.00	shopping	৳	2025-08-17	12:40:58.229511	2025-08	30522114904098519-1000.0-bought clo	2025-08-17 12:40:58.231052	messenger	Bought clothes for 1000 and then took an Uber for 100 more	
8	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	then took an uber for	100.00	transport	৳	2025-08-17	12:40:58.545761	2025-08	30522114904098519-100.0-then took 	2025-08-17 12:40:58.54741	messenger	Bought clothes for 1000 and then took an Uber for 100 more	
18	1e837186f19ad92f36b9f484b87093fb84875e4399440409ee88a6d2e0821b2d	bought clothes	1000.00	shopping	৳	2025-08-17	12:50:12.708899	2025-08	1e837186f19ad92f36b9f484b87093fb84875e4399440409ee88a6d2e0821b2d-1000-bought clo	2025-08-16 12:50:12.481562	messenger		
19	1e837186f19ad92f36b9f484b87093fb84875e4399440409ee88a6d2e0821b2d	uber ride	100.00	transport	৳	2025-08-17	12:50:12.708906	2025-08	1e837186f19ad92f36b9f484b87093fb84875e4399440409ee88a6d2e0821b2d-100-uber ride	2025-08-16 12:50:12.481562	messenger		
20	1e837186f19ad92f36b9f484b87093fb84875e4399440409ee88a6d2e0821b2d	lunch at restaurant	250.00	food	৳	2025-08-17	12:50:12.708908	2025-08	1e837186f19ad92f36b9f484b87093fb84875e4399440409ee88a6d2e0821b2d-250-lunch at r	2025-08-15 12:50:12.481562	messenger		
21	1e837186f19ad92f36b9f484b87093fb84875e4399440409ee88a6d2e0821b2d	coffee shop	80.00	food	৳	2025-08-17	12:50:12.70891	2025-08	1e837186f19ad92f36b9f484b87093fb84875e4399440409ee88a6d2e0821b2d-80-coffee sho	2025-08-14 12:50:12.481562	messenger		
22	1e837186f19ad92f36b9f484b87093fb84875e4399440409ee88a6d2e0821b2d	grocery shopping	500.00	food	৳	2025-08-17	12:50:12.708912	2025-08	1e837186f19ad92f36b9f484b87093fb84875e4399440409ee88a6d2e0821b2d-500-grocery sh	2025-08-13 12:50:12.481562	messenger		
23	1e837186f19ad92f36b9f484b87093fb84875e4399440409ee88a6d2e0821b2d	rent payment	1200.00	bills	৳	2025-08-17	12:50:12.708914	2025-08	1e837186f19ad92f36b9f484b87093fb84875e4399440409ee88a6d2e0821b2d-1200-rent payme	2025-08-12 12:50:12.481562	messenger		
24	1e837186f19ad92f36b9f484b87093fb84875e4399440409ee88a6d2e0821b2d	gas station	150.00	transport	৳	2025-08-17	12:50:12.708915	2025-08	1e837186f19ad92f36b9f484b87093fb84875e4399440409ee88a6d2e0821b2d-150-gas statio	2025-08-11 12:50:12.481562	messenger		
25	1e837186f19ad92f36b9f484b87093fb84875e4399440409ee88a6d2e0821b2d	dinner takeout	75.00	food	৳	2025-08-17	12:50:12.708918	2025-08	1e837186f19ad92f36b9f484b87093fb84875e4399440409ee88a6d2e0821b2d-75-dinner tak	2025-08-10 12:50:12.481562	messenger		
26	2628898427c719c3b2295fa0aa9cc7793e5c61ab3a211392fb6a4f830293f7ac	bought clothes	1000.00	shopping	৳	2025-08-17	12:51:22.542273	2025-08	2628898427c719c3b2295fa0aa9cc7793e5c61ab3a211392fb6a4f830293f7ac-1000-bought clo-1755427882.315947	2025-08-17 10:51:22.315947	messenger		
27	2628898427c719c3b2295fa0aa9cc7793e5c61ab3a211392fb6a4f830293f7ac	uber ride	100.00	transport	৳	2025-08-17	12:51:22.54228	2025-08	2628898427c719c3b2295fa0aa9cc7793e5c61ab3a211392fb6a4f830293f7ac-100-uber ride-1755427882.315947	2025-08-17 10:51:22.315947	messenger		
28	2628898427c719c3b2295fa0aa9cc7793e5c61ab3a211392fb6a4f830293f7ac	uber ride	500.00	transport	৳	2025-08-17	12:51:22.542282	2025-08	2628898427c719c3b2295fa0aa9cc7793e5c61ab3a211392fb6a4f830293f7ac-500-uber ride-1755431482.315947	2025-08-17 11:51:22.315947	messenger		
29	2628898427c719c3b2295fa0aa9cc7793e5c61ab3a211392fb6a4f830293f7ac	restaurant meal	250.00	food	৳	2025-08-17	12:51:22.542284	2025-08	2628898427c719c3b2295fa0aa9cc7793e5c61ab3a211392fb6a4f830293f7ac-250-restaurant-1755348682.315947	2025-08-16 12:51:22.315947	messenger		
30	2628898427c719c3b2295fa0aa9cc7793e5c61ab3a211392fb6a4f830293f7ac	coffee	75.00	food	৳	2025-08-17	12:51:22.542286	2025-08	2628898427c719c3b2295fa0aa9cc7793e5c61ab3a211392fb6a4f830293f7ac-75-coffee-1755262282.315947	2025-08-15 12:51:22.315947	messenger		
31	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	logged 2 expenses totaling	1100.00	other	৳	2025-08-17	12:58:08.469294	2025-08	30522114904098519-1100.0-logged 2 e	2025-08-17 12:58:08.47197	messenger	Logged 2 expenses totaling 1100.0: 1000.0 for bought clothes for, 100.0 for then took an uber for. Nice variety across shopping, transport!	
32	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	for then took an uber for	0.00	transport	৳	2025-08-17	12:58:08.788634	2025-08	30522114904098519-0.0-for then t	2025-08-17 12:58:08.789875	messenger	Logged 2 expenses totaling 1100.0: 1000.0 for bought clothes for, 100.0 for then took an uber for. Nice variety across shopping, transport!	
33	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	i did not log	15.00	other	৳	2025-08-17	12:59:13.65244	2025-08	30522114904098519-15.0-i did not 	2025-08-17 12:59:13.654589	messenger	I did not log 15 dollar coffee, I logged 100 taka coffee	
34	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	i logged	100.00	other	৳	2025-08-17	12:59:13.951695	2025-08	30522114904098519-100.0-i logged	2025-08-17 12:59:13.952988	messenger	I did not log 15 dollar coffee, I logged 100 taka coffee	
35	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	before	100.00	other	৳	2025-08-17	13:14:48.69945	2025-08	30522114904098519-100.0-before	2025-08-17 13:14:48.702278	messenger	I logged coffee 100 before	
36	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	now i drank coffee for	300.00	food	৳	2025-08-17	13:15:11.369148	2025-08	30522114904098519-300.0-now i dran	2025-08-17 13:15:11.370399	messenger	Now I drank coffee for 300 and bought a sandal for 1000	
37	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	bought a sandal for	1000.00	other	৳	2025-08-17	13:15:11.671687	2025-08	30522114904098519-1000.0-bought a s	2025-08-17 13:15:11.673006	messenger	Now I drank coffee for 300 and bought a sandal for 1000	
38	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	Now I took an Uber ride for	1000.00	other	৳	2025-08-17	13:15:49.273311	2025-08	30522114904098519-1000.0-Now I took	2025-08-17 13:15:49.274506	messenger	Now I took an Uber ride for 1000	
39	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	I drank water worth	10.00	other	৳	2025-08-17	13:16:24.198508	2025-08	30522114904098519-10.0-I drank wa	2025-08-17 13:16:24.199822	messenger	I drank water worth 10	
40	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	then i decided to gamble	10000.00	other	৳	2025-08-17	13:16:51.213591	2025-08	30522114904098519-10000.0-then i dec	2025-08-17 13:16:51.214811	messenger	Then I decided to gamble 10000 taka and lost everything	
41	3d8f054b90f38820b9d2988ce0692d4862b4750e4f63bda28fdc27d3798653ac	Shopping	1000.00	other	৳	2025-08-17	13:45:55.47394	2025-08	PSID_DEMO_001-1000.0-Shopping	2025-08-17 13:45:55.475572	messenger	Shopping 1000.0	
42	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	on Uber ride	100.00	other	৳	2025-08-17	13:53:18.231553	2025-08	30522114904098519-100.0-on Uber ri	2025-08-17 13:53:18.234071	messenger	I have also spent 100 on Uber ride	
43	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	on groceries	120.00	other	৳	2025-08-17	14:07:08.340336	2025-08	30522114904098519-120.0-on groceri	2025-08-17 14:07:08.342434	messenger	I spent 120 on groceries	
44	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	on Uber	100.00	other	৳	2025-08-17	14:07:21.152864	2025-08	30522114904098519-100.0-on Uber	2025-08-17 14:07:21.154031	messenger	I spent 100 on Uber	
48	9fd996fb33d85f3a749573efcb4054023ee1c6320383252fe471364f85c77595	Coffee	100.00	Food	৳	2025-08-18	05:35:19.562971	2025-08	test_exp_1	2025-08-18 05:35:19.562974	messenger	coffee 100	
49	9fd996fb33d85f3a749573efcb4054023ee1c6320383252fe471364f85c77595	Lunch	500.00	Food	৳	2025-08-18	05:35:19.56298	2025-08	test_exp_2	2025-08-18 05:35:19.562981	messenger	lunch 500	
55	9fd996fb33d85f3a749573efcb4054023ee1c6320383252fe471364f85c77595	Expense from: lunch 125 and parking 55	125.00	food	৳	2025-08-18	05:50:45.888144	2025-08	existing_test_user-125.0-Expense fr	2025-08-18 05:50:45.89337	messenger	lunch 125 and parking 55	
56	9fd996fb33d85f3a749573efcb4054023ee1c6320383252fe471364f85c77595	Expense from: lunch 125 and parking 55	55.00	other	৳	2025-08-18	05:50:47.986345	2025-08	existing_test_user-55.0-Expense fr	2025-08-18 05:50:47.987049	messenger	lunch 125 and parking 55	
78	a20425ef9abcb34401cd0f33773b7f5071bc2713885cf7f15b026e6fe26916ff	Expense from: Coffee 50	50.00	food	৳	2025-08-21	10:30:15.192966	2025-08	74d124cdff7b473b96d290a8600144f7	2025-08-21 10:30:15.197698	messenger	Coffee 50	
79	a20425ef9abcb34401cd0f33773b7f5071bc2713885cf7f15b026e6fe26916ff	Expense from: Lunch 300 at KFC	300.00	food	৳	2025-08-21	10:30:38.829467	2025-08	745eb0aa509e4ac48769fb9818b17545	2025-08-21 10:30:38.830031	messenger	Lunch 300 at KFC	
80	a20425ef9abcb34401cd0f33773b7f5071bc2713885cf7f15b026e6fe26916ff	Expense from: I took an Uber for 300 and then had coffee 50	300.00	transport	৳	2025-08-21	10:36:33.677065	2025-08	3a332d6214644b89899b1bef9350ff67	2025-08-21 10:36:33.681339	messenger	I took an Uber for 300 and then had coffee 50	
81	a20425ef9abcb34401cd0f33773b7f5071bc2713885cf7f15b026e6fe26916ff	Expense from: I took an Uber for 300 and then had coffee 50	50.00	food	৳	2025-08-21	10:36:33.677346	2025-08	a0dae073268e49cba46dfa42adaebd84	2025-08-21 10:36:33.681345	messenger	I took an Uber for 300 and then had coffee 50	
\.


--
-- Data for Name: monthly_summaries; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.monthly_summaries (id, user_id_hash, month, total_amount, expense_count, categories, ai_insights, created_at, updated_at) FROM stdin;
1	9406d3902955fd67c5bb9bdaa24bb580cf38f5821d8e6b7678ff6950156ba0ec	2025-08	700.00	3	{"food": 100.0}		2025-08-17 12:36:37.558054	2025-08-17 12:36:41.627812
2	fe9853b6f04f5ebcff7f52edab15c11b2f1cde64fa3544c7afdff6fc16ccffc5	2025-08	100.00	1	{"other": 100.0}		2025-08-17 12:36:48.172397	2025-08-17 12:36:48.172401
4	3d8f054b90f38820b9d2988ce0692d4862b4750e4f63bda28fdc27d3798653ac	2025-08	1000.00	1	{"other": 1000.0}		2025-08-17 13:45:57.499255	2025-08-17 13:45:57.499259
3	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	2025-08	15645.00	17	{"other": 100.0}		2025-08-17 12:40:16.279437	2025-08-17 14:07:21.28719
5	9fd996fb33d85f3a749573efcb4054023ee1c6320383252fe471364f85c77595	2025-08	180.00	2	{"food": 125.0}		2025-08-18 05:50:46.893037	2025-08-18 05:50:48.858089
\.


--
-- Data for Name: rate_limits; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.rate_limits (id, user_id_hash, platform, daily_count, hourly_count, last_daily_reset, last_hourly_reset, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.users (id, user_id_hash, platform, total_expenses, expense_count, created_at, last_interaction, last_user_message_at, daily_message_count, hourly_message_count, last_daily_reset, last_hourly_reset, is_new, has_completed_onboarding, onboarding_step, interaction_count, first_name, income_range, spending_categories, primary_category, focus_area, additional_info, preferences) FROM stdin;
6	0d3fa177980e821ba5442240e075d71e2d25eeda94ead19293c6b910f61b7e34	messenger	0.00	0	2025-08-17 12:36:32.051453	2025-08-17 12:36:34.068215	2025-08-17 12:36:32.051458	0	0	2025-08-17	2025-08-17 12:36:32.051469	f	t	5	16	TestUser	50000-100000	[]	food	budgeting	{}	{}
2	52ff5a50c7fe3d3da199b88b875f3a913053f4cdc60a39b42795c0294a4bbe6b	messenger	0.00	0	2025-08-17 12:19:32.217103	2025-08-18 05:57:07.554476	2025-08-18 05:57:07.554434	0	0	2025-08-17	2025-08-17 12:19:32.217117	f	t	0	56	there		[]			{}	{}
10	dc863d3aa69d518264428cadc7b19e19b5d723c980a0db219d8063a1746128dc	messenger	15645.00	17	2025-08-17 12:40:16.0199	2025-08-17 14:07:21.220332	2025-08-17 12:40:16.01991	0	0	2025-08-17	2025-08-17 12:40:16.019922	f	t	0	8	there		[]			{}	{}
1	f26fbedd8b17c25d7fc8dce194dab43cb9ed47dac06019f828520890e30dc693	messenger	0.00	0	2025-08-17 12:06:50.219213	2025-08-17 12:07:03.703699	2025-08-17 12:06:50.219218	0	0	2025-08-17	2025-08-17 12:06:50.219229	f	t	0	4	there		[]			{}	{}
8	67a8dd9df3ea336da323072f61428e4f6d615d601333180dcf2fc898a75081f9	messenger	0.00	0	2025-08-17 12:36:43.661354	2025-08-17 12:36:44.790493	2025-08-17 12:36:43.661359	0	0	2025-08-17	2025-08-17 12:36:43.661367	f	t	5	9	SimpleUser		[]			{}	{}
9	fe9853b6f04f5ebcff7f52edab15c11b2f1cde64fa3544c7afdff6fc16ccffc5	messenger	100.00	1	2025-08-17 12:36:46.594535	2025-08-17 12:36:47.721101	2025-08-17 12:36:46.594539	0	0	2025-08-17	2025-08-17 12:36:46.594546	t	f	0	0			[]			{}	{}
12	1e837186f19ad92f36b9f484b87093fb84875e4399440409ee88a6d2e0821b2d	messenger	0.00	0	2025-08-17 12:50:13.167723	2025-08-17 12:50:20.581479	2025-08-17 12:50:13.167727	0	0	2025-08-17	2025-08-17 12:50:13.167736	f	t	5	22	Alex		[]			{}	{}
29	a20425ef9abcb34401cd0f33773b7f5071bc2713885cf7f15b026e6fe26916ff	messenger	0.00	0	2025-08-18 13:06:56.258309	2025-08-21 10:54:16.407989	2025-08-21 10:54:16.407915	0	0	2025-08-18	2025-08-18 13:06:56.258326	t	f	0	0			[]			{}	{}
13	2628898427c719c3b2295fa0aa9cc7793e5c61ab3a211392fb6a4f830293f7ac	messenger	0.00	0	2025-08-17 12:51:23.000056	2025-08-17 12:51:35.603948	2025-08-17 12:51:23.000061	0	0	2025-08-17	2025-08-17 12:51:23.000072	f	t	5	19	TestUser		[]			{}	{}
20	c2bc4e9c04bf32e7b787b04e0ffb853036eb0582af6d20857a9ff14651480f3d	messenger	0.00	0	2025-08-18 05:34:00.234535	2025-08-18 05:34:00.234539	2025-08-18 05:34:00.23454	0	0	2025-08-18	2025-08-18 05:34:00.234552	t	f	1	0			[]			{}	{}
16	3d8f054b90f38820b9d2988ce0692d4862b4750e4f63bda28fdc27d3798653ac	messenger	1000.00	1	2025-08-17 13:45:55.928604	2025-08-17 13:45:57.045693	2025-08-17 13:45:55.92861	0	0	2025-08-17	2025-08-17 13:45:55.92862	t	f	0	0			[]			{}	{}
21	62cb0c8f3d9e4d98a52498d4e8998f191b889b6a1d119c3c94419dc5442d319d	messenger	0.00	0	2025-08-18 05:34:02.494747	2025-08-18 05:34:02.494751	2025-08-18 05:34:02.494752	0	0	2025-08-18	2025-08-18 05:34:02.494763	t	f	1	0			[]			{}	{}
15	6a7ec52218589b4b7a4343eebbc49180201fe94636d96fa95921d15352111b64	messenger	0.00	0	2025-08-17 13:45:39.57998	2025-08-17 13:45:59.965838	2025-08-17 13:45:39.579987	0	0	2025-08-17	2025-08-17 13:45:39.579996	f	t	0	5	there		[]			{}	{}
3	5ab07c4d33055f652cc2980bfaeee74eda2f7b1a03e45ad6a45ca2e38757dc9b	messenger	0.00	0	2025-08-17 12:33:48.914863	2025-08-17 12:33:49.391567	2025-08-17 12:33:48.914867	0	0	2025-08-17	2025-08-17 12:33:48.914877	t	f	1	1	there		[]			{}	{}
14	a9edadfbad99433d9c41a635dbabb2ad1c09dd46ca1acac5130267f7e92d70df	messenger	0.00	0	2025-08-17 13:04:55.55231	2025-08-17 13:38:20.089052	2025-08-17 13:04:55.552316	0	0	2025-08-17	2025-08-17 13:04:55.552328	f	t	0	19	there		[]			{}	{}
22	555f79928755b031f6f83969b917c43dcd7ec61ffca8460c6de3946da60f2733	messenger	0.00	0	2025-08-18 05:34:04.801434	2025-08-18 05:34:04.801438	2025-08-18 05:34:04.801438	0	0	2025-08-18	2025-08-18 05:34:04.801447	t	f	1	0			[]			{}	{}
4	a403bd3e6e80efd84dc55cd3197159d9481d776da03d11447856ecd3c9c6d1cc	messenger	0.00	0	2025-08-17 12:33:56.791481	2025-08-17 12:33:57.259328	2025-08-17 12:33:56.791485	0	0	2025-08-17	2025-08-17 12:33:56.791494	t	f	1	1	there		[]			{}	{}
7	9406d3902955fd67c5bb9bdaa24bb580cf38f5821d8e6b7678ff6950156ba0ec	messenger	700.00	3	2025-08-17 12:36:35.973845	2025-08-17 13:46:53.309904	2025-08-17 12:36:35.97385	0	0	2025-08-17	2025-08-17 12:36:35.973857	t	f	1	1	there		[]			{}	{}
23	cab82e972543bb0750c0d2a6d920eca58279b5d5338c1ec98ae057e2b79e6ad0	messenger	0.00	0	2025-08-18 05:34:07.075676	2025-08-18 05:34:07.075679	2025-08-18 05:34:07.07568	0	0	2025-08-18	2025-08-18 05:34:07.075688	t	f	1	0			[]			{}	{}
5	17404010ae93ae466355bd116196a879a496a8cedbc89afa1db89f0d4dbf4f78	messenger	0.00	0	2025-08-17 12:35:10.172803	2025-08-17 12:35:40.362957	2025-08-17 12:35:10.172808	0	0	2025-08-17	2025-08-17 12:35:10.17282	t	f	0	2			[]			{}	{}
25	3d0c1e9da946e13aa70d0968c99b12ad653222ee81b2e25fa00e17d39df9054b	messenger	0.00	0	2025-08-18 05:39:23.242288	2025-08-18 05:39:23.242292	2025-08-18 05:39:23.242293	0	0	2025-08-18	2025-08-18 05:39:23.242304	t	f	1	0			[]			{}	{}
26	2b72d60d7e581b399e61d1057cbf8c17faeb4310f58f1d54e14efeb84e29b6ed	messenger	0.00	0	2025-08-18 05:40:57.024272	2025-08-18 05:40:57.024276	2025-08-18 05:40:57.024277	0	0	2025-08-18	2025-08-18 05:40:57.02429	t	f	1	0			[]			{}	{}
27	f7021dcf5a75ec9bdce565eb8b50f36dcc7ac885936c173c5d34af05404cc95f	messenger	0.00	0	2025-08-18 05:49:22.394953	2025-08-18 05:49:22.394956	2025-08-18 05:49:22.394957	0	0	2025-08-18	2025-08-18 05:49:22.394966	t	f	1	0			[]			{}	{}
28	56725a10b45a9519a3d2f7882b0a289c6bcee44c2c3309f7eebb44d2ad096adf	messenger	0.00	0	2025-08-18 06:55:24.318433	2025-08-18 12:42:21.419098	2025-08-18 12:42:21.419062	0	0	2025-08-18	2025-08-18 06:55:24.31845	t	f	0	0			[]			{}	{}
24	9fd996fb33d85f3a749573efcb4054023ee1c6320383252fe471364f85c77595	messenger	1680.00	7	2025-08-18 05:35:19.7981	2025-08-18 05:50:48.422464	2025-08-18 05:35:19.798106	0	0	2025-08-18	2025-08-18 05:35:19.798114	t	t	0	1		5000-10000	[]			{}	{}
17	61e7c8a1667b564352e41c0d382434f18282d458173d671bc128163048ac530f	messenger	0.00	0	2025-08-18 05:14:37.764109	2025-08-18 05:14:37.766135	2025-08-18 05:14:37.766137	0	0	2025-08-18	2025-08-18 05:14:37.766148	t	f	0	0	UAT		[]			{}	{}
30	c0aec21089c1f230032a08006a2c4a3b1f2fe1d73dbb3057096981a1f7ef75fa	messenger	0.00	0	2025-08-20 15:33:12.859543	2025-08-20 15:33:12.859544	2025-08-20 15:33:12.857131	0	0	2025-08-20	2025-08-20 15:33:12.85956	t	f	0	0			[]			{}	{}
\.


--
-- Name: expenses_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.expenses_id_seq', 81, true);


--
-- Name: monthly_summaries_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.monthly_summaries_id_seq', 5, true);


--
-- Name: rate_limits_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.rate_limits_id_seq', 1, false);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.users_id_seq', 30, true);


--
-- Name: expenses expenses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_pkey PRIMARY KEY (id);


--
-- Name: monthly_summaries monthly_summaries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.monthly_summaries
    ADD CONSTRAINT monthly_summaries_pkey PRIMARY KEY (id);


--
-- Name: rate_limits rate_limits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rate_limits
    ADD CONSTRAINT rate_limits_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_user_id_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_user_id_hash_key UNIQUE (user_id_hash);


--
-- Name: idx_expenses_user_id_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_expenses_user_id_created_at ON public.expenses USING btree (user_id, created_at DESC);


--
-- Name: idx_users_psid_hash_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_users_psid_hash_unique ON public.users USING btree (user_id_hash);


--
-- Name: idx_users_user_id_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_users_user_id_hash ON public.users USING btree (user_id_hash);


--
-- PostgreSQL database dump complete
--

