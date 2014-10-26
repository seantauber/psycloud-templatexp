"""`main` is the top level module for your Flask application."""

import os
import json

from psycloudclient import PsycloudClient
psycloud_client = PsycloudClient("http://psycloud-server-1.appspot.com")

# Import the Flask Framework
from flask import Flask, render_template, request, redirect, url_for, abort, jsonify

app = Flask(__name__)
# Note: We don't need to call run() since our application is embedded within
# the App Engine WSGI application server.

@app.route('/<exp_type>/start/<experiment_id>')
def coupon_landing(exp_type, experiment_id):
	return render_template('%s/registration_with_coupon.html'%exp_type, exp=experiment_id, exp_type=exp_type)

@app.route('/cregister', methods=['POST'])
def register_with_coupon():
	exp_id = request.form['exp']
	exp_type = request.form['exp_type']
	reg_coupon = request.form['reg_coupon']
	result = psycloud_client.register(exp_id, registration_coupon=reg_coupon)
	if result['status'] == 200:
		participant_id = result['result']['participant']['short_id']
		return render_template('%s/instructions.html'%exp_type, uid=participant_id, exp_type=exp_type)
	elif result['status'] == 400 and result['result'] == "Duplicate registration coupon":
		return render_template('%s/duplicate_notify.html'%exp_type)
	else:
		return jsonify(result)


@app.route('/experiment', methods=['POST'])
def experiment():

	participant_id = request.form['uid']
	exp_type = request.form['exp_type']
	# participant = psycloud_client.get_participant(participant_id)

	if "responses" in request.form:
		form_keys = request.form.keys()
		resp_keys = []
		for key in form_keys:
			s = key.split('_')
			if s[0] == 'resp':
				resp_keys.append( [ s[1], int(s[2]), key ] )
		resp_keys.sort()
		r = {}
		for key in resp_keys:
			name = key[0]
			if r.has_key(name):
				r[name].append(request.form[key[2]])
			else:
				r[name] = [request.form[key[2]]]

		previous_response_variables = r
	else:
		previous_response_variables = None

	if previous_response_variables is None:
		result = psycloud_client.get_current_stimulus(participant_id)
	
	else:
		result = psycloud_client.save_current_response(participant_id, {'variables':previous_response_variables})
		
		if result['status'] == 200:
			result = psycloud_client.increment_and_get_next_stimulus(participant_id)
		else:
			# return bad_request("Unable to save to database. Please contact the experiment administrator.")
			return jsonify(result)

	if result['status'] == 200:
		stimulus = result['result']['stimuli'][0]
		stimulus_template = stimulus['stimulus_type'] + '.html'
		stimulus_variables = stimulus['variables']
		return render_template('%s/%s'%(exp_type, stimulus_template), exp_type=exp_type,
			uid=participant_id, stim=stimulus_variables, prev=previous_response_variables)
	else:
		result = psycloud_client.completed(participant_id)
		if result['status'] == 200:
			return render_template('%s/post_experiment.html'%exp_type, verification_code=participant_id)
		else:
			return jsonify(result)


# @app.route('/test/<exp_type>/<template_type>', methods=['GET'])
# def instructions_test(exp_type, template_type):
# 	# exp_type = 'mammals'
# 	uid = 'part_uid'
# 	return render_template('%s/%s.html'%(exp_type,template_type), uid=uid, exp_type=exp_type)

@app.route('/submitresponse', methods=['POST'])
def test_response():
	return json.dumps(request.form)


def bad_request(e):
    return jsonify( {'status':400, 'message':'Bad Request', 'result':e}), 400

@app.errorhandler(404)
def page_not_found(e):
    """Return a custom 404 error."""
    return 'Sorry, Nothing at this URL.', 404


@app.errorhandler(500)
def page_not_found(e):
    """Return a custom 500 error."""
    return 'Sorry, unexpected error: {}'.format(e), 500
