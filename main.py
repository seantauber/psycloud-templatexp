"""`main` is the top level module for your Flask application."""

import os
import json

from psycloud_python.client import PsycloudClient
from psycloud_python.custom_exceptions import DuplicateEntryError, ResourceError

cfg_file = open('server.cfg')
cfg = json.load(cfg_file)
cfg_file.close()

psycloud_client = PsycloudClient(cfg['server_url'])

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

	try:
		participant_id = psycloud_client.register(exp_id, registration_coupon=reg_coupon)
	
	except DuplicateEntryError:
		return render_template('%s/duplicate_notify.html'%exp_type)
	
	except ResourceError:
		abort(410)
	
	except Exception, e:
		return bad_request(e)
	
	else:
		return render_template('%s/instructions.html'%exp_type, uid=participant_id, exp_type=exp_type)


@app.route('/experiment', methods=['POST'])
def experiment():

	participant_id = request.form['uid']
	exp_type = request.form['exp_type']

	current_stim = psycloud_client.get_current_stimulus(participant_id)
	max_stim = psycloud_client.get_max_stimulus_count(participant_id) - 1
	r = None # This will contain the previous response variables if they exist but defaults to None

	if current_stim > 0:

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

			# r now contains a dictionary of response variables... so save it.
			try:
				saved_response = psycloud_client.save_response(participant_id, current_stim - 1, r)
			except:
				abort(500)
			
			if current_stim < max_stim:
				# increment current stimulus
				try:
					success = psycloud_client.set_current_stimulus(participant_id, current_stim + 1)
				except:
					abort(500)
				else:
					if success:
						current_stim += 1
					else:
						abort(500)
			else:
				# Experiment is over
				conf_code = psycloud_client.get_confirmation_code(participant_id)
				return render_template('%s/post_experiment.html'%exp_type, verification_code=conf_code)

		else:
			# current stimulus is >0 but there was no response data... they probably reloaded
			# or navigated back to the page. So load the current stimuli without saving a response
			# and without incrementing the stimulus counter
			pass


	try:
		# Get the stimulus
		stimulus = psycloud_client.get_stimulus(participant_id, current_stim)
	except:
		abort(500)
	else:

		#Extract the stimulus information and render the template
		
		stimulus_template = stimulus['stimulus_type'] + '.html'
		stimulus_variables = stimulus['variables']

		return render_template('%s/%s'%(exp_type, stimulus_template), exp_type=exp_type,
			uid=participant_id, stim=stimulus_variables, prev=r)




@app.route('/submitresponse', methods=['POST'])
def test_response():
	return json.dumps(request.form)


def bad_request(e):
    return jsonify( {'status':400, 'message':'Bad Request', 'result':e}), 400

@app.errorhandler(404)
def page_not_found(e):
    """Return a custom 404 error."""
    return 'Sorry, Nothing at this URL.', 404


@app.errorhandler(410)
def experiment_full(e):
    return jsonify( {'status':410, 'message':'Experiment full.'}), 410


@app.errorhandler(500)
def page_not_found(e):
    """Return a custom 500 error."""
    return 'Sorry, unexpected error: {}'.format(e), 500
